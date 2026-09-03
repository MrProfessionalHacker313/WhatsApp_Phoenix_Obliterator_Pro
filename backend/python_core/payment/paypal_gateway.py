"""
PHOENIX EAGLE — PAYPAL PAYMENT GATEWAY
======================================
PayPal REST API integration built on the standard ``requests`` library plus an
IPN (Instant Payment Notification) verifier.

Responsibilities
----------------
* Obtain an OAuth2 access token against the PayPal REST API.
* Create and capture PayPal orders for the three plans.
* Verify IPN callbacks against PayPal so only genuinely completed payments
  trigger license issuance.

Setup
-----
Environment variables (never hard-code secrets):
    PAYPAL_CLIENT_ID
    PAYPAL_CLIENT_SECRET
    PAYPAL_MODE        "sandbox" (default) or "live"
    PAYPAL_BASE       override the API base URL if needed

Note: PayPal's Orders v2 webhooks supersede the legacy IPN channel; we provide
both an OAuth2 order "capture" flow for the checkout UI and a classic IPN
verifier for server-to-server notification.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .config import CONFIG, PLANS
from .emailer import send_license_email

logger = logging.getLogger("phoenix.payment.paypal")


def _craft_paypal_id() -> str:
    import uuid
    return f"paypal_{uuid.uuid4().hex[:16]}"


def _paypal_custom_fields(custom_str: str) -> dict:
    """
    Parse PayPal's ``custom`` field, tolerating both the legacy plain-string
    form (``"basic"``) and the JSON form we now emit (``{"plan":..,"ref":..}``).
    Returns {plan, ref}.
    """
    from .config import LicenseTier
    if not custom_str:
        return {"plan": LicenseTier.BASIC, "ref": ""}
    try:
        data = json.loads(custom_str)
        if isinstance(data, dict):
            return {"plan": str(data.get("plan") or LicenseTier.BASIC),
                    "ref": str(data.get("ref") or "")}
    except Exception:
        pass
    # Legacy: custom used to carry the bare plan key.
    return {"plan": str(custom_str), "ref": ""}


def _paypal_settle_referral(form: dict, txn_id: str) -> None:
    """Credit the referrer (if any) from a PayPal payment form."""
    parsed = _paypal_custom_fields(form.get("custom") or "")
    ref = parsed["ref"]
    if not ref:
        return
    try:
        mc_gross = float(form.get("mc_gross") or 0.0)
        amount_cents = int(round(mc_gross * 100)) or 0
    except (TypeError, ValueError):
        amount_cents = 0
    from sharing.affiliate_tracker import get_tracker
    get_tracker().settle_referral(
        ref_code=ref, amount_cents=amount_cents,
        plan_key=parsed["plan"],
        payment_id=txn_id or _craft_paypal_id(),
        billing_reason="purchase",
    )


def _paypal_settle_referral_capture(ref_code: str, plan_key: str,
                                 payment_id: str) -> None:
    """Credit the referrer from a captured PayPal order."""
    from sharing.affiliate_tracker import get_tracker
    try:
        get_tracker().settle_referral(
            ref_code=ref_code, amount_cents=0, plan_key=plan_key,
            payment_id=payment_id, billing_reason='purchase')
    except Exception as exc:
        logger.warning('Affiliate settlement failed for %s: %s', ref_code, exc)




class PayPalAuthError(RuntimeError):
    """Raised when PayPal authentication or order operations fail."""


class PayPalGateway:
    """Wrapper over PayPal's REST Orders v2 and the IPN verifier."""

    def __init__(self):
        self.access_token: str | None = None
        self.token_expires: float = 0.0

    # ------------------------------------------------------------- auth
    def _get_access_token(self, force: bool = False) -> str:
        """Fetch a fresh OAuth2 client-credentials token for PayPal."""
        if self.access_token and not force and self.token_expires > 0:
            return self.access_token

        resp = requests.post(
            f"{CONFIG.paypal_api_base}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json",
                     "Accept-Language": "en_US"},
            auth=(CONFIG.paypal_client_id, CONFIG.paypal_client_secret),
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error("PayPal token request failed: %d %s",
                         resp.status_code, resp.text)
            raise PayPalAuthError(
                f"PayPal authentication failed ({resp.status_code})")
        data = resp.json()
        self.access_token = data.get("access_token", "")
        from time import time
        self.token_expires = time() + int(data.get("expires_in", 3600)) - 60
        return self.access_token

    # ------------------------------------------------------------- orders
    def create_order(self, plan_key: str, return_url: str,\
                     cancel_url: str, customer_email: str = "",
                     ref_code: str = "") -> dict:
        """
        Create a PayPal order for ``plan_key``. Returns the PayPal order object
        with an approve link for the buyer.

        ``ref_code`` (from a share link) is stored in the PayPal ``custom``
        field so IPN / capture can attribute the sale to the referrer.
        """
        plan = PLANS.get(plan_key)
        if not plan:
            raise ValueError(f"Unknown plan: {plan_key}")

        token = self._get_access_token()
        purchase_unit: dict = {
            "reference_id": plan_key,
            "amount": {
                "currency_code": "USD",
                "value": f"{plan.price_cents / 100:.2f}",
            },
            "description": f"Phoenix Eagle {plan.display_name} license "
                           f"({plan.duration_days} days)",
        }
        if ref_code:
            purchase_unit["custom"] = json.dumps({"plan": plan_key, "ref": ref_code})
        body = {
            "intent": "CAPTURE",
            "purchase_units": [purchase_unit],
            "application_context": {
                "brand_name": "Phoenix Eagle",
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "PAY_NOW",
            },
        }
        if customer_email:
            body["payer"] = {"email_address": customer_email}

        resp = requests.post(
            f"{CONFIG.paypal_api_base}/v2/checkout/orders",
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            logger.error("PayPal order creation failed: %d %s",
                         resp.status_code, resp.text)
            raise PayPalAuthError(
                f"PayPal order creation failed ({resp.status_code})")

        order = resp.json()
        approve_link = ""
        for link in order.get("links", []):
            if link.get("rel") == "approve":
                approve_link = link.get("href", "")
                break
        return {"order": order, "approve_url": approve_link}

    def capture_order(self, order_id: str) -> dict:
        """Capture an approved PayPal order. Returns the capture result."""
        token = self._get_access_token()
        resp = requests.post(
            f"{CONFIG.paypal_api_base}/v2/checkout/orders/{order_id}/capture",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            logger.error("PayPal order capture failed: %d %s",
                         resp.status_code, resp.text)
            raise PayPalAuthError(
                f"PayPal order capture failed ({resp.status_code})")
        return resp.json()

    def get_order(self, order_id: str) -> dict:
        """Retrieve an order's current state (status/completion)."""
        token = self._get_access_token()
        resp = requests.get(
            f"{CONFIG.paypal_api_base}/v2/checkout/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code != 200:
            raise PayPalAuthError(
                f"PayPal order lookup failed ({resp.status_code})")
        return resp.json()
# ------------------------------------------------------------- IPN
    def verify_ipn(self, form: dict, raw: str) -> bool:
        """
        Verify a classic PayPal IPN notification.

        We POST the notification back to PayPal's IPN endpoint with
        "cmd=_notify-validate" appended; PayPal replies "VERIFIED" or
        "INVALID". Returns True only on a VERIFIED confirmation.
        """
        payload = dict(form)
        payload["cmd"] = "_notify-validate"
        resp = requests.post(
            # Restore any spaces the form decoding may have collapsed.
            CONFIG.paypal_ipn_verify_url,
            data=payload,
            headers={"User-Agent": "Python-PayPal-IPN/1.0"},
            timeout=15,
        )
        return resp.text.strip() == "VERIFIED"

    def handle_ipn(self, form: dict, raw: str) -> dict:
        """
        Handle a verified IPN notification for license issuance.

        Only ``payment_status == 'Completed'`` licenses. Also logs failures.
        Returns {verified, processed, license_key, plan}.
        """
        verified = self.verify_ipn(form, raw)
        if not verified:
            logger.warning("IPN verification FAILED for txn %s",
                           form.get("txn_id"))
            return {"verified": False, "processed": False,
                    "license_key": None, "plan": None}

        payment_status = form.get("payment_status", "").upper()
        if payment_status != "COMPLETED":
            logger.info("IPN received but status is %s — not issuing license",
                        payment_status)
            return {"verified": True, "processed": False,
                    "license_key": None, "plan": None}

        txn_id = form.get("txn_id") or "unknown"
        custom_fields = _paypal_custom_fields(form.get("custom") or "")
        plan_key = custom_fields["plan"]

        # Reuse the Stripe gateway's registry helper for idempotency.
        from .stripe_gateway import StripeGateway
        registry = StripeGateway()
        already = registry.lookup_license(txn_id)
        if already:
            logger.info("IPN already processed (idempotent): %s", txn_id)
            # Still ensure the affiliate is credited if first time.
            _paypal_settle_referral(form, txn_id)
            return {"verified": True, "processed": True,
                    "license_key": already.get("key"), "plan": plan_key}

        from .license_manager import LicenseManager
        manager = LicenseManager()
        payload = manager.generate_license(
            tier=plan_key,
            customer_email=form.get("payer_email", ""),
        )
        key = manager.human_license_key(payload)
        registry.register_license(txn_id, {
            "key": key,
            "payload": payload,
            "plan": plan_key,
            "email": form.get("payer_email", ""),
            "gross": form.get("mc_gross", ""),
            "created": payload.get("issued"),
        })
        _paypal_settle_referral(form, txn_id)
        logger.info("License issued for PayPal txn %s (tier=%s)", txn_id, plan_key)
        return {"verified": True, "processed": True,
                "license_key": key, "plan": plan_key}

    # ------------------------------------------------------- license issuance
    def issue_license_for_capture(self, order_id: str) -> dict:
        """After a successful capture, confirm completion and issue a license."""
        order = self.capture_order(order_id)
        status = (order.get("status") or "").upper()
        reference = ""
        ref_code = ""
        for unit in order.get("purchase_units", []):
            unit_custom = unit.get("custom") or ""
            parsed = _paypal_custom_fields(unit_custom)
            reference = parsed["plan"]
            if parsed["ref"]:
                ref_code = parsed["ref"]
        if status != "COMPLETED":
            if ref_code:
                _paypal_settle_referral_capture(ref_code, reference, order_id)
            return {"issued": False, "status": status, "license_key": None,
                    "plan": reference or None}
        from .stripe_gateway import StripeGateway
        from .license_manager import LicenseManager
        registry = StripeGateway()
        existing = registry.lookup_license(order_id)
        if existing:
            if ref_code:
                _paypal_settle_referral_capture(ref_code, reference, order_id)
            return {"issued": True, "status": status,
                    "license_key": existing.get("key"), "plan": reference}
        manager = LicenseManager()
        payload = manager.generate_license(tier=reference or "basic")
        key = manager.human_license_key(payload)
        registry.register_license(order_id, {
            "key": key, "payload": payload, "plan": reference})
        send_license_email(
            to_email="", license_key=key, plan_name=reference,
            tier=reference or "basic", expires_at=payload.get("expires", ""))
        if ref_code:
            _paypal_settle_referral_capture(ref_code, reference, order_id)
        return {"issued": True, "status": status, "license_key": key,
                "plan": reference}
