"""
PHOENIX EAGLE — SHARE LINK FLASK SERVER BLUEPRINT
==================================================
A Flask blueprint that serves the permanent share links.

Routes
------
    GET  /activate/<ref_code>          Beautiful landing page for a share link.
    GET  /activate?ref=...             Same page when ?ref= is used.
    GET  /api/share/<ref_code>         JSON details for a share link.
    GET  /api/affiliate/<id>           Affiliate dashboard (JSON).
    POST /api/affiliate/register       Create an affiliate account.
    POST /api/affiliate/withdraw       Request a payout.
    GET  /buy/<ref_code>               Start a Stripe checkout with attribution.

The blueprint is self-contained so it can be registered onto any Flask app
(including the existing payment server) via ``app.register_blueprint(...)``.
"""

from __future__ import annotations

import logging
import os

from flask import Blueprint, jsonify, render_template, request

from payment.config import PLANS
from payment.stripe_gateway import StripeGateway

from .affiliate_tracker import AffiliateTracker
from .link_generator import (
    ShareLinkGenerator,
    parse_ref_code,
)

logger = logging.getLogger("phoenix.sharing.server")

# Directory holding this package's templates.
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


class ShareLinkServer:
    """
    Encapsulates the routes + domain wiring for the share-link system,
    so a blueprint can be built without re-wiring collaborators each time.
    """

    def __init__(self, generator: ShareLinkGenerator | None = None,
                 tracker: AffiliateTracker | None = None,
                 plan_loader=PLANS):
        self.generator = generator or ShareLinkGenerator()
        self.tracker = tracker or AffiliateTracker()
        self.plan_loader = plan_loader

    # ------------------------------------------------------------------ routes
    def activate_view(self, ref_code: str):
        parsed = parse_ref_code(ref_code)
        record = self.generator.get(ref_code) if parsed["valid"] else None
        if not record:
            return _render_not_found(ref_code), 404

        plans = [
            {"key": p.key, "name": p.name, "display_name": p.display_name,
             "price_usd": p.price_usd, "duration_days": p.duration_days,
             "perks": list(p.perks)}
            for p in self.plan_loader.values()
        ]
        return render_template(
            "activate.html",
            record=record,
            license_key=record.get("license_key", ""),
            ref=record.get("ref", ""),
            price_usd=record.get("price_usd", ""),
            plan_display=record.get("plan_display", ""),
            download_url=record.get("download_url", "") or "#",
            product_name="Phoenix Eagle Ultra Pro",
            tagline="World's #1 WhatsApp Engine",
            referral_url=record.get("url", ""),
            share_channels=record.get("share_templates", {}),
            plans=plans,
            referrer=record.get("affiliate", ""),
        )

    def api_share(self, ref_code: str):
        parsed = parse_ref_code(ref_code)
        record = self.generator.get(ref_code) if parsed["valid"] else None
        if not record:
            return _json({"ok": False, "error": "Unknown share link"}, 404)
        # Never leak the raw signed payload to anonymous callers; expose a
        # sanitised public view.
        public = {
            "ok": True,
            "ref": record["ref"],
            "url": record["url"],
            "plan": record["plan"],
            "plan_display": record["plan_display"],
            "price_usd": record["price_usd"],
            "price_cents": record["price_cents"],
            "duration_days": record["duration_days"],
            "download_url": record.get("download_url", ""),
            "share_templates": record.get("share_templates", {}),
            "expires": record.get("expires"),
        }
        return _json(public)
    def api_affiliate(self, affiliate_id: str):
        dash = self.tracker.dashboard(affiliate_id)
        if not dash.get("affiliate"):
            return _json({"ok": False, "error": "Unknown affiliate"}, 404)
        return _json({"ok": True, "dashboard": dash})

    def api_register_affiliate(self):
        data = _json_body()
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        if not name or not email:
            return _json({"ok": False, "error": "name and email required"}, 400)
        affiliate = self.tracker.register_affiliate(
            name=name,
            email=email,
            stripe_connected_account=(data.get("stripe_connected_account") or ""),
        )
        return _json({"ok": True, "affiliate": affiliate})

    def api_withdraw(self):
        data = _json_body()
        affiliate_id = (data.get("affiliate_id") or "").strip()
        try:
            amount_cents = int(data.get("amount_cents", 0) or 0)
        except Exception:
            amount_cents = 0
        try:
            wd = self.tracker.request_withdrawal(affiliate_id, amount_cents)
            return _json({"ok": True, "withdrawal": wd})
        except ValueError as exc:
            return _json({"ok": False, "error": str(exc)}, 400)

    # ------------------------------------------------------------ checkout
    def buy_view(self, ref_code: str):
        """Start a Stripe checkout session carrying the referrer attribution."""
        parsed = parse_ref_code(ref_code)
        record = self.generator.get(ref_code) if parsed["valid"] else None
        if not record:
            return _json({"ok": False, "error": "Unknown share link"}, 404)
        plan = (data_request("plan") or record["plan"] or "basic")
        base = os.environ.get("PAYMENT_BASE_URL", "http://127.0.0.1:8787")
        try:
            gw = StripeGateway()
            session = gw.create_checkout_session(
                plan_key=plan,
                success_url=f"{base.rstrip('/')}/checkout/success?plan={plan}",
                cancel_url=f"{base.rstrip('/')}/activate/{ref_code}",
                metadata={"ref": ref_code, "plan": plan},
            )
            session["ref"] = ref_code
            return _json({"ok": True, "session": session})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)}, 500)


def data_request(key: str) -> str:
    """Read ``key`` from JSON body or query string (defensive)."""
    try:
        body = request.get_json(silent=True) or {}
        return body.get(key) or request.args.get(key) or ""
    except Exception:
        return request.args.get(key) or ""


def _json_body() -> dict:
    if not request.data:
        return {}
    try:
        return request.get_json(silent=True) or {}
    except Exception:
        return {}


def _json(obj, status: int = 200):
    return (jsonify(obj), status)


def _render_not_found(ref_code: str):
    return render_template(
        "activate.html",
        record=None,
        license_key="",
        ref=ref_code or "",
        product_name="Phoenix Eagle Ultra Pro",
        not_found=True,
    )


def create_share_blueprint(name: str = "sharing") -> Blueprint:
    """
    Build a Flask blueprint exposing the share-link + affiliate routes.

    Register onto any app: ``app.register_blueprint(create_share_blueprint())``.
    Templates + assets are resolved from this package's ``templates`` dir.
    """
    server = ShareLinkServer()
    bp = Blueprint(name, __name__, template_folder=TEMPLATE_DIR,
                   static_folder=None, url_prefix="/")

    bp.add_url_rule("/activate/<path:ref_code>", "activate",
                    server.activate_view, methods=["GET"])
    bp.add_url_rule("/activate", "activate_query",
                    lambda: _handle_activate_query(server), methods=["GET"])
    bp.add_url_rule("/buy/<ref_code>", "buy", server.buy_view,
                    methods=["GET", "POST"])
    bp.add_url_rule("/api/share/<ref_code>", "api_share",
                    server.api_share, methods=["GET"])
    bp.add_url_rule("/api/affiliate/<affiliate_id>", "api_affiliate",
                    server.api_affiliate, methods=["GET"])
    bp.add_url_rule("/api/affiliate/register", "api_register_affiliate",
                    server.api_register_affiliate, methods=["POST"])
    bp.add_url_rule("/api/affiliate/withdraw", "api_withdraw",
                    server.api_withdraw, methods=["POST"])
    return bp


def _handle_activate_query(server: ShareLinkServer):
    ref = (request.args.get("ref") or "").strip()
    if not ref:
        return _render_not_found(""), 404
    return server.activate_view(ref)