"""
PHOENIX EAGLE — AFFILIATE / REFERRAL TRACKER
============================================
Tracks which referrer shared which link, computes the recurring 10%
commission on every paid sale, and manages payouts through Stripe.

Responsibilities
----------------
* Register affiliates (a referrer needs an affiliate account + Stripe
  connected account to be paid).
* Attribute a sale to a referrer when a purchase completes through one of
  their share links (the gateway calls :func:`settle_referral`).
* Calculate a 10% recurring commission on each qualifying sale. Because the
  BASIC/PRO plans are sold as *recurring* subscriptions, every renewal is
  credited to the referrer who brought the customer in — 10% recurring.
* Withdrawals: an affiliate requests a payout; the tracker creates a Stripe
  Transfer to the affiliate's connected account (or a Payout for Express
  accounts) and records it for the dashboard.
* Expose an affiliate dashboard (JSON + optional HTML) summarising earnings,
  pending balance, payouts and referral links.

Stripe integration is lazy and optional: if ``STRIPE_SECRET_KEY`` is unset the
tracker operates in a "sandbox" mode where balances accrue locally and payout
records are created without moving money — ideal for local development.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .storage import (
    AFFILIATES,
    ASSETS,
    COMMISSIONS,
    SALES_LOG,
    WITHDRAWALS,
    ShareStore,
)

logger = logging.getLogger("phoenix.sharing.affiliate")

# ---------------------------------------------------------------------------
# Constants (shared with the CLI and the dashboard)
# ---------------------------------------------------------------------------
# Recurring commission rate: 10% of every qualifying sale.
COMMISSION_RATE = 0.10


class CommissionStatus:
    PENDING = "pending"
    RECURRING = "recurring"
    PAYOUT_REQUESTED = "payout_requested"
    PAID = "paid"


class WithdrawalStatus:
    REQUESTED = "requested"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _craft_id(prefix: str) -> str:
    """Return a short, unique record id built from a UUID (underscores only)."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _stripe_api():
    """Optional Stripe integration; returns None when not configured."""
    try:
        import stripe
    except Exception:
        return None
    from payment.config import CONFIG
    if not CONFIG.stripe_secret_key:
        return None
    stripe.api_key = CONFIG.stripe_secret_key
    try:
        stripe.api_version = CONFIG.stripe_api_version
    except Exception:
        pass
    return stripe
class AffiliateTracker:
    """
    Server-side orchestration of affiliates, commissions and withdrawals.
    All state persists atomically via the sharing JSON stores.
    """

    def __init__(
        self,
        affiliates: ShareStore | None = None,
        commissions: ShareStore | None = None,
        withdrawals: ShareStore | None = None,
        sales: ShareStore | None = None,
        links_store: ShareStore | None = None,
    ):
        self.affiliates = affiliates or AFFILIATES
        self.commissions = commissions or COMMISSIONS
        self.withdrawals = withdrawals or WITHDRAWALS
        self.sales = sales or SALES_LOG
        # Links store is used for attribution (share_links.json).
        self._links_store = links_store

    # =================================================================
    # Affiliate accounts
    # =================================================================
    def register_affiliate(
        self,
        name: str,
        email: str,
        stripe_connected_account: str = "",
        payout_method: str = "stripe_transfer",
    ) -> dict:
        """Create (or update) an affiliate account. Returns the account."""
        email = (email or "").strip().lower()
        account_id = ""
        # Reuse the existing id if the email is already registered.
        for aid, rec in self.affiliates.all().items():
            if rec.get("email", "").lower() == email and isinstance(rec, dict):
                account_id = aid
                break
        if not account_id:
            account_id = _craft_id("aff")
        affiliate = self.affiliates.get(account_id, {})
        affiliate.update({
            "id": account_id,
            "name": (name or "").strip(),
            "email": email,
            "stripe_connected_account": stripe_connected_account,
            "payout_method": payout_method,
            "balance_cents": int(affiliate.get("balance_cents", 0)),
            "created": affiliate.get("created", _now()),
        })
        self.affiliates.set(account_id, affiliate)
        return affiliate

    def get_affiliate(self, affiliate_id: str) -> dict | None:
        rec = self.affiliates.get(affiliate_id)
        return rec if isinstance(rec, dict) else None

    def affiliate_by_ref(self, ref_code: str) -> dict | None:
        """Return the affiliate owning a given share link (if any)."""
        record = self._link_record(ref_code)
        if not record or not record.get("affiliate"):
            return None
        return self.get_affiliate(record["affiliate"])

    # =================================================================
    # Attribution: register a sale created through a share link
    # =================================================================
    def settle_referral(
        self,
        ref_code: str,
        amount_cents: int,
        plan_key: str = "basic",
        payment_id: str = "",
        billing_reason: str = "purchase",
    ) -> dict:
        """
        Credit the referrer a 10% commission for a sale made through their link.

        This is the automatic hook called by the payment gateway webhook when
        a ``checkout.session.completed`` (or subscription renewal) arrives. The
        sale is idempotent per ``payment_id`` so retried webhooks never double-
        credit the referrer.

        Returns {credited, affiliate_id, commission_cents, ref}}.
        """
        plan_key = (plan_key or "basic")
        payment_id = payment_id or _craft_id("sale")

        # Guard non-purchase events: never credit for failed/uncaptured money.
        if billing_reason not in ("purchase", "subscription_create",
                                  "subscription_update", "subscription_cycle"):
            return {"credited": False, "reason": "not_a_payable_event"}

        affiliate = self.affiliate_by_ref(ref_code)
        if not affiliate:
            return {"credited": False, "reason": "no_affiliate", "ref": ref_code}

        # Idempotency: no double credit for the same payment/cycle.
        if self._sale_credited(payment_id, ref_code):
            return {"credited": True, "already": True,
                    "affiliate_id": affiliate["id"],
                    "commission_cents": self.sale_commission(payment_id)}

        commission_cents = int(round(amount_cents * COMMISSION_RATE))

        # Record the sale (audit trail).
        self.sales.set(payment_id, {
            "payment_id": payment_id,
            "ref": ref_code,
            "affiliate_id": affiliate["id"],
            "amount_cents": amount_cents,
            "commission_cents": commission_cents,
            "plan": plan_key,
            "billing_reason": billing_reason,
            "credited_at": _now(),
        })

        # Credit the recurring commission to the affiliate balance.
        self.commissions.set(payment_id, {
            "id": _craft_id("comm"),
            "payment_id": payment_id,
            "affiliate_id": affiliate["id"],
            "ref_code": ref_code,
            "amount_cents": amount_cents,
            "commission_cents": commission_cents,
            "rate": COMMISSION_RATE,
            "plan": plan_key,
            "billing_reason": billing_reason,
            "status": CommissionStatus.PENDING,
            "credited_at": _now(),
        })

        self._bump_balance(affiliate["id"], commission_cents)

        logger.info("Credited affiliate %s %d cents for sale %s (ref %s)",
                    affiliate["id"], commission_cents, payment_id, ref_code)
        return {"credited": True, "already": False,
                "affiliate_id": affiliate["id"],
                "commission_cents": commission_cents, "ref": ref_code}
    # ------------------------------------------------------------------ accounting
    def sale_commission(self, payment_id: str) -> int:
        rec = self.commissions.get(payment_id)
        if rec:
            return int(rec.get("commission_cents", 0))
        sale = self.sales.get(payment_id)
        return int(sale.get("commission_cents", 0)) if sale else 0

    def _sale_credited(self, payment_id: str, ref_code: str) -> bool:
        # Idempotency: the same payment/cycle is never credited twice.
        return self.sales.contains(payment_id)

    def _link_record(self, ref_code: str) -> dict | None:
        """Look up the share link record owning a ref code."""
        if self._links_store is not None:
            rec = self._links_store.get(ref_code)
            return rec if isinstance(rec, dict) else None
        try:
            from .storage import SHARE_LINKS
            rec = SHARE_LINKS.get(ref_code)
            return rec if isinstance(rec, dict) else None
        except Exception:
            return None

    def _bump_balance(self, affiliate_id: str, amount_cents: int) -> None:
        def _add(rec: dict) -> dict:
            rec["balance_cents"] = int(rec.get("balance_cents", 0)) + amount_cents
            rec["lifetime_earned_cents"] = int(
                rec.get("lifetime_earned_cents", 0)) + amount_cents
            return rec
        self.affiliates.mutate(affiliate_id, _add)

    # =================================================================
    # Dashboard / stats
    # =================================================================
    def dashboard(self, affiliate_id: str) -> dict:
        """Return the affiliate dashboard payload for one affiliate."""
        affiliate = self.get_affiliate(affiliate_id) or {}
        comms = [c for c in self.commissions.all().values()
                 if isinstance(c, dict) and c.get("affiliate_id") == affiliate_id]
        paid = sum(int(c.get("commission_cents", 0)) for c in comms
                   if c.get("status") == CommissionStatus.PAID)
        pending = sum(int(c.get("commission_cents", 0)) for c in comms
                      if c.get("status") in (
                          CommissionStatus.PENDING,
                          CommissionStatus.RECURRING,
                          CommissionStatus.PAYOUT_REQUESTED))
        wd = [w for w in self.withdrawals.all().values()
              if isinstance(w, dict) and w.get("affiliate_id") == affiliate_id]
        links = self._links_for_affiliate(affiliate_id)
        return {
            "affiliate": affiliate,
            "stats": {
                "balance_cents": int(affiliate.get("balance_cents", 0)),
                "lifetime_earned_cents": int(
                    affiliate.get("lifetime_earned_cents", 0)),
                "paid_cents": paid,
                "pending_cents": pending,
                "commission_rate": COMMISSION_RATE,
                "sales_count": len(comms),
                "total_commissions_cents": sum(
                    int(c.get("commission_cents", 0)) for c in comms),
            },
            "commissions": comms,
            "withdrawals": wd,
            "share_links": links,
        }

    def _links_for_affiliate(self, affiliate_id: str) -> list[dict]:
        try:
            from .storage import SHARE_LINKS
        except Exception:
            return []
        rows = []
        for rec in SHARE_LINKS.all().values():
            if isinstance(rec, dict) and rec.get("affiliate") == affiliate_id:
                rows.append({k: rec.get(k) for k in (
                    "ref", "url", "plan", "plan_display", "price_usd",
                    "duration_days", "download_url", "created")})
        return rows
    # =================================================================
    # Withdrawals (Stripe Payouts / Transfers)
    # =================================================================
    def request_withdrawal(self, affiliate_id: str, amount_cents: int) -> dict:
        """Create a payout request for an affiliate's partial balance."""
        affiliate = self.get_affiliate(affiliate_id)
        if not affiliate:
            raise ValueError(f"Unknown affiliate: {affiliate_id}")
        balance = int(affiliate.get("balance_cents", 0))
        if amount_cents <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount_cents > balance:
            raise ValueError(
                f"Requested {amount_cents} exceeds available balance {balance}")

        withdrawal_id = _craft_id("wd")
        record = {
            "id": withdrawal_id,
            "affiliate_id": affiliate_id,
            "amount_cents": amount_cents,
            "fee_cents": 0,
            "net_cents": amount_cents,
            "status": WithdrawalStatus.REQUESTED,
            "payout_id": None,
            "requested_at": _now(),
            "processed_at": None,
        }
        self.withdrawals.set(withdrawal_id, record)
        # Freeze the requested funds so they cannot be double-spent.
        self._bump_balance(affiliate_id, -amount_cents)
        logger.info("Withdrawal requested for %s: %d cents",
                    affiliate_id, amount_cents)
        return record

    def process_withdrawals(self) -> list[dict]:
        """
        Pay out every REQUESTED withdrawal via Stripe (Transfer + Payout).

        Returns the list of processed withdrawal records. When Stripe is not
        configured, withdrawals are marked PAID in the local ledger (sandbox).
        """
        stripe = _stripe_api()
        processed: list[dict] = []
        for wd_id, wd in self.withdrawals.all().items():
            if not isinstance(wd, dict) or \
                    wd.get("status") != WithdrawalStatus.REQUESTED:
                continue
            affiliate = self.get_affiliate(wd.get("affiliate_id", ""))
            result = self._execute_payout(wd, affiliate, stripe)
            processed.append(result)
        return processed

    def _execute_payout(self, wd: dict, affiliate: dict | None,
                        stripe) -> dict:
        """Mark one withdrawal as paid; move money when Stripe is available."""
        if stripe is None or not affiliate:
            wd["status"] = WithdrawalStatus.PAID
            wd["payout_id"] = None
            wd["processed_at"] = _now()
            wd["sandbox"] = True
        else:
            try:
                payout_id = self._stripe_transfer(
                    stripe, affiliate, wd,
                    affiliate.get("stripe_connected_account", ""))
                wd["status"] = WithdrawalStatus.PAID
                wd["payout_id"] = payout_id
                wd["processed_at"] = _now()
                wd["sandbox"] = False
            except Exception as exc:  # surface the failure in the dashboard
                logger.error("Stripe payout failed for %s: %s", wd["id"], exc)
                wd["status"] = WithdrawalStatus.FAILED
                wd["error"] = str(exc)
                wd["processed_at"] = _now()
        self.withdrawals.set(wd["id"], wd)
        return wd

    def _stripe_transfer(self, stripe, affiliate: dict, wd: dict,
                         connected_account: str) -> str:
        """Create a Stripe Transfer + Payout; returns the payout id."""
        if not connected_account:
            raise RuntimeError("Affiliate has no Stripe connected account")
        # Transfer funds to the connected account...
        transfer = stripe.Transfer.create(
            amount=wd["amount_cents"],
            currency="usd",
            destination=connected_account,
            description=f"Phoenix Eagle affiliate payout {wd['id']}",
        )
        # ...then pay them out of that connected account.
        payout = stripe.Payout.create(
            amount=wd["amount_cents"],
            currency="usd",
            destination=connected_account,
            description=f"Phoenix Eagle affiliate payout {wd['id']}",
            stripe_account=connected_account,
        )
        return payout.id

    def withdrawal_status(self, withdrawal_id: str) -> dict | None:
        wd = self.withdrawals.get(withdrawal_id)
        return wd if isinstance(wd, dict) else None


# ---------------------------------------------------------------------------
# Module-level convenience singleton (mirrors the CONFIG-style convention).
# ---------------------------------------------------------------------------
_tracker = AffiliateTracker()


def get_tracker() -> AffiliateTracker:
    return _tracker