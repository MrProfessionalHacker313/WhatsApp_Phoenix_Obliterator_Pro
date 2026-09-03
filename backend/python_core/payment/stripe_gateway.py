"""
PHOENIX EAGLE — STRIPE PAYMENT GATEWAY
======================================
Production-ready Stripe integration using the official ``stripe`` SDK (v15+).

Responsibilities
----------------
* Create Stripe Checkout Sessions for one-time and recurring (subscription)
  payments for the three plans.
* Verify webhooks via signature, handle payment success/failure, and
  automatically issue a hardware-locked license on successful payment.
* Manage subscriptions (monthly/yearly) mapped to license tiers.

Setup
-----
Set these environment variables (never hard-code secrets):
    STRIPE_SECRET_KEY        sk_live_...
    STRIPE_PUBLISHABLE_KEY   pk_live_...
    STRIPE_WEBHOOK_SECRET    whsec_...
    PAYMENT_BASE_URL         e.g. https://pay.example.com

Design notes
------------
* ``checkout.session.completed`` is the only trustworthy signal that funds
  moved. We never auto-issue a license from a client-side callback.
* Idempotency: each successful payment maps to one license UUID via a local
  registry file, so retried webhooks do not double-issue.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .config import CONFIG, PLANS, LicenseTier
from .emailer import send_license_email

logger = logging.getLogger("phoenix.payment.stripe")


def _session_amount_cents(session: dict) -> int:
    """Extract the charged amount (in cents) from a Stripe checkout session."""
    amount = session.get("amount_total") or session.get("amount")
    if amount is not None:
        try:
            return int(amount)
        except (TypeError, ValueError):
            return 0
    # Walk the line items as a defensive fallback.
    for item in (session.get("display_items") or session.get("line_items") or []):
        amt = item.get("amount")
        if amt is not None:
            return int(amt)
    return 0



def _stripe_api() -> Any:
    """Return the stripe module, configuring it lazily from the environment."""
    import stripe  # local import keeps the CLI fast when Stripe is not used
    stripe.api_key = CONFIG.stripe_secret_key
    try:
        stripe.api_version = CONFIG.stripe_api_version
    except Exception:
        pass
    return stripe


class StripeGateway:
    """Thin, defensive wrapper over the Stripe Python SDK."""

    def __init__(self, registry_path: str | None = None):
        self.registry_path = registry_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "licenses_issued.json")
        self._registry = self._load_registry()

    # ------------------------------------------------------------- registry
    def _load_registry(self) -> dict:
        try:
            if os.path.exists(self.registry_path):
                with open(self.registry_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning("Could not load license registry: %s", exc)
        return {}

    def _save_registry(self) -> None:
        try:
            tmp = self.registry_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._registry, fh, indent=2)
            os.replace(tmp, self.registry_path)
        except Exception as exc:
            logger.error("Could not persist license registry: %s", exc)

    def register_license(self, payment_id: str, license_dict: dict) -> None:
        self._registry[payment_id] = license_dict
        self._save_registry()

    def lookup_license(self, payment_id: str) -> dict | None:
        return self._registry.get(payment_id)

    # ------------------------------------------------------- checkout session
    def create_checkout_session(
        self,
        plan_key: str,
        customer_email: str = "",
        mode: str = "payment",
        subscription_interval: str = "month",
        success_url: str | None = None,
        cancel_url: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """
        Create a Checkout Session for ``plan_key``.

        ``mode``       : "payment" for a one-time charge or "subscription" for
                         recurring billing.
        ``interval``   : "month" or "year" (used only in subscription mode).
        Returns {id, url, client_reference_id}.
        """
        plan = PLANS.get(plan_key)
        if not plan:
            raise ValueError(f"Unknown plan: {plan_key}")

        stripe = _stripe_api()
        base = CONFIG.base_url
        success_url = success_url or f"{base}/checkout/success?plan={plan_key}"
        cancel_url = cancel_url or f"{base}/checkout/checkout.html"

        line_items = [{
            "price_data": {
                "currency": "usd",
                "unit_amount": plan.price_cents,
                "product_data": {
                    "name": f"Phoenix Eagle — {plan.display_name}",
                    "description": f"{plan.name} license "
                                   f"({plan.duration_days} days)",
                },
            },
            "quantity": 1,
        }]

        session_params: dict[str, Any] = {
            "mode": mode,
            "line_items": line_items,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": plan_key,
        }
        if customer_email:
            session_params["customer_email"] = customer_email
        if metadata:
            session_params["metadata"] = metadata

        try:
            session = stripe.checkout.Session.create(**session_params)
            return {
                "id": session.id,
                "url": session.url,
                "client_reference_id": plan_key,
                "mode": mode,
            }
        except Exception as exc:
            logger.error("Stripe checkout creation failed: %s", exc)
            raise
# ------------------------------------------------------------- webhooks
    def handle_webhook(self, payload: bytes, sig_header: str) -> dict:
        """
        Verify and process a Stripe webhook event.

        Returns a summary {received, event_type, payment_id, license_key, plan}.
        """
        stripe = _stripe_api()
        webhook_secret = CONFIG.stripe_webhook_secret
        if not webhook_secret:
            raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret)
        except Exception as exc:
            logger.warning("Stripe webhook signature verification failed: %s", exc)
            raise ValueError(f"Invalid signature: {exc}")

        event_type = event["type"]
        summary = {
            "received": True,
            "event_type": event_type,
            "payment_id": None,
            "license_key": None,
            "plan": None,
        }

        if event_type == "checkout.session.completed":
            summary = self._on_checkout_completed(event)
        elif event_type == "customer.subscription.created":
            self._on_subscription_created(event)
        elif event_type in ("customer.subscription.deleted",
                            "customer.subscription.paused"):
            self._on_subscription_ended(event)

        return summary

    def _on_checkout_completed(self, event: dict) -> dict:
        session = event["data"]["object"]
        payment_id = session.get("payment_intent") or session.get(
            "id", "unknown")
        plan_key = (session.get("client_reference_id")
                    or (session.get("metadata") or {}).get("plan", "basic"))
        plan = PLANS.get(plan_key)
        tier = plan.key if plan else LicenseTier.BASIC
        # Attribution: the share-link checkout session carries ``ref`` in its
        # metadata; credit the referrer a 10% recurring commission on every
        # successful payment (idempotent — retried webhooks are a no-op).
        ref_code = (session.get("metadata") or {}).get("ref", "")
        if ref_code:
            try:
                from sharing.affiliate_tracker import get_tracker
                amount_cents = _session_amount_cents(session)
                get_tracker().settle_referral(
                    ref_code=ref_code, amount_cents=amount_cents,
                    plan_key=plan_key, payment_id=payment_id,
                    billing_reason="purchase")
            except Exception as comm_exc:
                logger.warning("Affiliate settlement failed for %s: %s",
                               ref_code, comm_exc)


        already = self.lookup_license(payment_id)
        if already:
            logger.info("Payment already licensed (idempotent): %s", payment_id)
            return {
                "received": True,
                "event_type": event["type"],
                "payment_id": payment_id,
                "license_key": already.get("key"),
                "plan": plan_key,
            }

        # Auto-issue a hardware-locked license for the paid plan.
        from .license_manager import LicenseManager
        manager = LicenseManager()
        payload = manager.generate_license(
            tier=tier,
            customer_email=session.get("customer_email", ""),
        )
        key = manager.human_license_key(payload)
        self.register_license(payment_id, {
            "key": key,
            "payload": payload,
            "plan": plan_key,
            "email": session.get("customer_email", ""),
            "created": payload.get("issued"),
        })
        logger.info("License auto-issued for payment %s (tier=%s)",
                    payment_id, tier)
        try:
            send_license_email(
                to_email=session.get("customer_email", ""),
                license_key=key,
                plan_name=plan.name if plan else plan_key,
                tier=tier,
                expires_at=payload.get("expires", ""),
            )
        except Exception as email_exc:
            logger.warning("License email dispatch failed: %s", email_exc)
        return {
            "received": True,
            "event_type": event["type"],
            "payment_id": payment_id,
            "license_key": key,
            "plan": plan_key,
        }

    # ---------------------------------------------------------- subscriptions
    def create_subscription_price(self, plan_key: str) -> str:
        """
        Create/return a recurring Price for a plan on the default product.
        Returns the Price id. Requires Stripe products/prices setup.
        """
        plan = PLANS.get(plan_key)
        if not plan:
            raise ValueError(f"Unknown plan: {plan_key}")
        stripe = _stripe_api()
        price_id = self.lookup_license(f"price_{plan_key}") or ""
        if price_id:
            return price_id

        product = stripe.Product.create(
            name=f"Phoenix Eagle {plan.name} Subscription")
        price = stripe.Price.create(
            product=product.id,
            currency="usd",
            unit_amount=plan.price_cents,
            recurring={"interval": "month"},
        )
        self.register_license(f"price_{plan_key}", {"price": price.id})
        return price.id

    def _on_subscription_created(self, event: dict) -> None:
        sub = event["data"]["object"]
        logger.info("Subscription created: %s (%s)",
                    sub.get("id"), sub.get("status"))

    def _on_subscription_ended(self, event: dict) -> None:
        sub = event["data"]["object"]
        logger.info("Subscription ended: %s (reminder: revoke license)",
                    sub.get("id"))