"""
PHOENIX EAGLE — PAYMENT & LICENSING FLASK SERVER
================================================
A small, secure Flask server that ties the CLI's checkout page, the Stripe and
PayPal gateways, and license activation together.

Routes
------
    GET  /                       Serve the eagle-themed checkout page
    GET  /api/plans              List available pricing plans (JSON)
    POST /api/create-checkout-session   Create a Stripe Checkout Session
    POST /api/create-paypal-order       Create a PayPal order
    POST /api/capture-paypal-order      Capture a completed PayPal order
    POST /api/activate-license          Validate + persist a license key
    POST /api/verify-license            Verify a supplied license key
    POST /stripe/webhook                Stripe webhook endpoint (signature checked)
    POST /paypal/webhook                PayPal IPN endpoint

Run with:
    python -m payment.payment_server    # or call create_app() in your worker
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from .config import CONFIG, PLANS, LicenseStatus
from .license_manager import LicenseManager

logger = logging.getLogger("phoenix.payment.server")

# Stored registry used by the gateways for idempotent license issuance.
REGISTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "licenses_issued.json")


def _register_license(payment_id: str, license_dict: dict) -> None:
    """Persist an issued license key to the shared registry (idempotency)."""
    data = {}
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = {}
    data[payment_id] = license_dict
    tmp = REGISTRY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, REGISTRY_PATH)


def _lookup_license(payment_id: str) -> dict | None:
    if not os.path.exists(REGISTRY_PATH):
        return None
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh).get(payment_id)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> Flask:
    """Build and configure the Flask application."""
    app = Flask(__name__, template_folder="templates",
                static_folder=None)

    # Register the public-permanent share-link + affiliate blueprint so the
    # payment server also serves /activate/<ref> and /api/affiliate/<id>.
    try:
        from sharing.link_server import create_share_blueprint
        app.register_blueprint(create_share_blueprint())
    except Exception as _share_exc:  # sharing is an optional add-on
        logging.getLogger("phoenix.payment.server").warning(
            "Could not register share blueprint: %s", _share_exc)

    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "templates")

    @app.route("/", methods=["GET"])
    @app.route("/checkout/checkout.html", methods=["GET"])
    def checkout_page():
        return send_from_directory(assets_dir, "checkout.html")

    @app.route("/checkout/success", methods=["GET"])
    def checkout_success():
        plan = request.args.get("plan", "basic")
        return f"<h1>Payment received</h1><p>Plan: {plan}. Your license has \
been generated and emailed.</p>"

    # ---------------- plans ----------------
    @app.route("/api/plans", methods=["GET"])
    def api_plans():
        return jsonify({
            "plans": [
                {
                    "key": p.key,
                    "name": p.name,
                    "display_name": p.display_name,
                    "price_usd": p.price_usd,
                    "price_cents": p.price_cents,
                    "duration_days": p.duration_days,
                    "recurring": p.recurring,
                    "lifetime_updates": p.lifetime_updates,
                    "perks": list(p.perks),
                }
                for p in PLANS.values()
            ]
        })

    # ---------------- Stripe checkout ----------------
    @app.route("/api/create-checkout-session", methods=["POST"])
    def api_create_checkout():
        from .stripe_gateway import StripeGateway
        body = _json_body()
        plan = body.get("plan", "basic")
        email = body.get("email", "")
        mode = body.get("mode", "payment")
        try:
            gw = StripeGateway()
            session = gw.create_checkout_session(
                plan_key=plan, customer_email=email, mode=mode)
            return jsonify({"ok": True, "session": session})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    # ---------------- PayPal order ----------------
    @app.route("/api/create-paypal-order", methods=["POST"])
    def api_create_paypal_order():
        from .paypal_gateway import PayPalGateway
        body = _json_body()
        plan = body.get("plan", "basic")
        email = body.get("email", "")
        base = CONFIG.base_url
        try:
            gw = PayPalGateway()
            result = gw.create_order(
                plan_key=plan,
                return_url=f"{base}/api/capture-paypal-order?plan={plan}",
                cancel_url=f"{base}/checkout/checkout.html",
                customer_email=email,
            )
            return jsonify({"ok": True, "approve_url": result["approve_url"],
                            "order_id": result["order"].get("id")})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/capture-paypal-order", methods=["POST"])
    def api_capture_paypal_order():
        from .paypal_gateway import PayPalGateway
        body = _json_body()
        order_id = body.get("order_id", "")
        try:
            gw = PayPalGateway()
            result = gw.issue_license_for_capture(order_id)
            return jsonify({"ok": True, "result": result})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    # ---------------- License activation ----------------
    @app.route("/api/activate-license", methods=["POST"])
    def api_activate_license():
        body = _json_body()
        key = (body.get("key") or "").strip()
        if not key:
            return jsonify({"ok": False,
                            "error": "No license key provided"}), 400
        try:
            manager = LicenseManager()
            result = manager.activate(key, persist=False)
            return jsonify({
                "ok": bool(result["valid"]),
                "valid": bool(result["valid"]),
                "status": result["status"],
                "tier": result["tier"],
                "expires_at": result["expires_at"],
                "remaining_days": result["remaining_days"],
                "reason": result["reason"],
            })
        except ValueError as exc:
            return jsonify({"ok": False, "status": LicenseStatus.INVALID,
                            "error": str(exc)}), 200
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/verify-license", methods=["POST"])
    def api_verify_license():
        body = _json_body()
        key = (body.get("key") or "").strip()
        if not key:
            return jsonify({"ok": False,
                            "error": "No license key provided"}), 400
        try:
            manager = LicenseManager()
            payload = manager.decode_license_key(key)
            result = manager.validate(payload, force_offline=True)
            return jsonify({
                "valid": bool(result["valid"]),
                "status": result["status"],
                "tier": result["tier"],
                "expires_at": result["expires_at"],
                "remaining_days": result["remaining_days"],
                "reason": result["reason"],
            })
        except ValueError as exc:
            return jsonify({"valid": False, "status": LicenseStatus.INVALID,
                            "reason": str(exc)}), 200
        except Exception as exc:
            return jsonify({"valid": False,
                            "reason": f"Verification error: {exc}"}), 200

    # ---------------- Stats ----------------
    @app.route("/api/stats", methods=["GET"])
    def api_stats():
        try:
            from core.engine import phoenix
            stats = phoenix.get_stats()
        except Exception:
            stats = {
                "total_operations": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
            }
        return jsonify(stats)

    # ---------------- Operation execution ----------------
    @app.route("/api/operation", methods=["POST"])
    def api_operation():
        body = _json_body()
        phone = (body.get("phone") or "").strip()
        action = (body.get("action") or "").strip().lower()
        duration = body.get("duration")
        if not phone or not action:
            return jsonify({"ok": False, "error": "phone and action are required"}), 400
        allowed = {
            "permanent_ban", "permanent_unban",
            "temporary_ban", "temporary_unban", "status_check",
        }
        if action not in allowed:
            return jsonify({"ok": False, "error": f"Unknown action: {action}"}), 400
        try:
            from core.engine import phoenix
            options = None
            if action == "temporary_ban" and duration is not None:
                options = {"duration": int(duration)}
            report = phoenix.process_number(phone, action, options=options)
            return jsonify({
                "ok": True,
                "success": bool(report.get("success")),
                "operation_id": report.get("operation_id"),
                "message": report.get("analysis", {}).get("strategy", {}).get("name", "Done"),
                "error": report.get("error"),
                "duration_seconds": report.get("duration_seconds"),
            })
        except Exception as exc:
            logger.exception("Operation failed")
            return jsonify({"ok": False, "error": str(exc)}), 500

    # ---------------- Webhooks ----------------
    @app.route("/stripe/webhook", methods=["POST"])
    def stripe_webhook():
        from .stripe_gateway import StripeGateway
        payload = request.data
        sig = request.headers.get("Stripe-Signature", "")
        try:
            gw = StripeGateway()
            summary = gw.handle_webhook(payload, sig)
            return jsonify(summary)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            logger.exception("Stripe webhook error")
            return jsonify({"error": str(exc)}), 500

    @app.route("/paypal/webhook", methods=["POST"])
    def paypal_webhook():
        from .paypal_gateway import PayPalGateway
        form = request.form.to_dict(flat=True)
        try:
            gw = PayPalGateway()
            summary = gw.handle_ipn(form, request.get_data(as_text=True))
            return jsonify(summary)
        except Exception as exc:
            logger.exception("PayPal IPN error")
            return jsonify({"error": str(exc)}), 500

    return app


def _json_body() -> dict:
    """Return parsed JSON request body (defensive)."""
    if not request.data:
        return {}
    try:
        return request.get_json(silent=True) or {}
    except Exception:
        return {}