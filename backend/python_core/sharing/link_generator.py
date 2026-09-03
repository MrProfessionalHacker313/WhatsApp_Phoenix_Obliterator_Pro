"""
PHOENIX EAGLE — PERMANENT SHARE LINK GENERATOR
==============================================
Creates public, permanent, unique share links of the form:

    https://phoenixeagle.pro/activate?ref=PHX-XXXX-XXXX

Design
------
* **Permanent & unique.** The ``ref`` code is a short, collision-resistant
  token (derived from a UUID) stored forever in the share registry
  (``share_links.json``). It is never tied to an expiry date.
* **Embedded license information.** Creating a link issues a real, RSA-2048
  signed license via ``payment.license_manager``. The signed license key and
  its line items (tier, price, duration) are attached to the share record and
  displayed on the landing page.
* **Attribution ready.** Every link may carry an owning ``affiliate_id`` so the
  affiliate tracker can credit commissions when a purchase completes through it.
* **Share channels.** Ready-made copy templates for WhatsApp, Email, SMS and
  Telegram are generated so the referrer can paste the link instantly.

Formatting
----------
The public display code ``PHX-XXXX-XXXX`` is a short, human-friendly token that
maps to the full signed license stored in the registry. Keeping the full key
server-side keeps the ref short while the embedded license stays valid.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from payment.config import PLANS, LicenseTier
from payment.license_manager import LicenseManager

from .storage import SHARE_LINKS, ShareStore

logger = logging.getLogger("phoenix.sharing.links")

# Public base URL rendered into generated links. Overridable so local testing
# can produce localhost links without re-typing them.
PUBLIC_BASE_URL = os.environ.get("SHARE_BASE_URL", "https://phoenixeagle.pro")
ACTIVATE_PATH = "/activate"

# Length of each dashed group in the public ref code.
GROUP_LEN = 4
REFS_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no confusing 0/O, 1/I


def generate_ref_code() -> str:
    """Return a permanent, unique public ref code of the form PHX-XXXX-XXXX."""
    def _group() -> str:
        return "".join(secrets.choice(REFS_CHARSET) for _ in range(GROUP_LEN))
    return f"PHX-{_group()}-{_group()}"


def parse_ref_code(ref: str) -> dict:
    """
    Strictly parse/validate a ref code.

    Returns {ref, valid}. ``valid`` is True only for well-formed ``PHX-XXXX-XXXX``.
    """
    ref = (ref or "").strip()
    match = re.fullmatch(r"PHX-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}", ref)
    if not match:
        return {"ref": ref, "valid": False}
    return {"ref": ref, "valid": True}


def build_share_url(ref_code: str) -> str:
    """Compose the permanent public URL for a given ref code."""
    base = PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{ACTIVATE_PATH}?ref={ref_code}"


# ---------------------------------------------------------------------------
# Share channel copy templates
# ---------------------------------------------------------------------------
SHARE_CHANNELS = ("whatsapp", "email", "sms", "telegram")


def _build_whatsapp(record: dict) -> str:
    return (
        f"*🦅 Phoenix Eagle Ultra Pro* — World's #1 WhatsApp Engine\n"
        f"🔗 Your License: {record['ref']}\n"
        f"📥 Download: {record['url']}\n"
        f"💰 Price: {record['price_usd']}\n"
        f"Permanent link — never expires: {record['url']}"
    )


def _build_telegram(record: dict) -> str:
    return (
        f"🦅 *Phoenix Eagle Ultra Pro*\n"
        f"🔗 License: `{record['ref']}`\n"
        f"📥 {record['url']}\n"
        f"💰 {record['price_usd']} · Permanent link"
    )


def _build_email(record: dict) -> str:
    return (
        f"Subject: Your Phoenix Eagle Ultra Pro License ({record['ref']})\n\n"
        f"Here is your permanent Phoenix Eagle license link. It never expires "
        f"and includes your embedded license + direct download.\n\n"
        f"   License : {record['ref']}\n"
        f"   Download: {record['url']}\n"
        f"   Price   : {record['price_usd']}\n\n"
        f"— Phoenix Security Labs 🦅"
    )


def _build_sms(record: dict) -> str:
    return (
        f"Phoenix Eagle Ultra Pro — License {record['ref']}. "
        f"Permanent link (never expires): {record['url']}"
    )


def build_share_templates(record: dict) -> dict:
    """Return copy-paste messages for each supported share channel."""
    return {
        "whatsapp": _build_whatsapp(record),
        "email": _build_email(record),
        "sms": _build_sms(record),
        "telegram": _build_telegram(record),
    }
class ShareLinkGenerator:
    """
    Author + persist permanent share links and the licenses they embed.
    """

    def __init__(self, store: ShareStore | None = None,
                 license_manager: LicenseManager | None = None):
        self.store = store or SHARE_LINKS
        # A license manager constructed here must be able to *sign* (i.e. run
        # where the RSA private key lives) so new links carry a real key.
        self.license_manager = license_manager or LicenseManager()

    # ----------------------------------------------------------- the core
    def create_share_link(
        self,
        plan_key: str = LicenseTier.BASIC,
        affiliate_id: str = "",
        customer_email: str = "",
        download_url: str = "",
        ref_code: str | None = None,
    ) -> dict:
        """
        Issue a permanent share link.

        Returns the link record: {ref, url, license_key, plan, price_usd,
        affiliate, download_url, created, share_templates, ...}
        """
        if plan_key != LicenseTier.TRIAL and plan_key not in PLANS:
            raise ValueError(f"Unknown plan for share link: {plan_key}")
        plan = PLANS.get(plan_key)

        # 1) A real, signed license embedded in the link. A blank machine
        #    binding lets the recipient bind to their own hardware on first
        #    activation (the offline verifier re-checks the digest then).
        payload = self.license_manager.generate_license(
            tier=plan_key,
            customer_email=customer_email,
            machine_id="",
        )
        license_key = self.license_manager.human_license_key(payload)

        # 2) A short, permanent, unique public ref code.
        code = ref_code or generate_ref_code()
        while self.store.contains(code):
            code = generate_ref_code()

        created = datetime.now(timezone.utc).isoformat()
        record = {
            "ref": code,
            "url": build_share_url(code),
            "license_key": license_key,
            "license_payload": payload,
            "plan": plan_key,
            "plan_display": (plan.display_name if plan else plan_key).title(),
            "price_usd": (plan.price_usd if plan else ""),
            "price_cents": (plan.price_cents if plan else 0),
            "duration_days": (plan.duration_days if plan else 0),
            "affiliate": affiliate_id,
            "download_url": download_url,
            "created": created,
            # Permanent: never expires.
            "expires": None,
        }
        record["share_templates"] = build_share_templates(record)
        self.store.set(code, record)
        logger.info("Created permanent share link %s for plan %s",
                    code, plan_key)
        return record

    # ------------------------------------------------------------- lookups
    def get(self, ref_code: str) -> dict | None:
        """Return the link record for a ref code, or None if unknown."""
        record = self.store.get(ref_code)
        return record if isinstance(record, dict) else None

    # ----------------------------------------------------------- helper CLI
    def list_links(self) -> list[dict]:
        """Return every permanent link record (for admin/dashboard use)."""
        return [r for r in self.store.all().values() if isinstance(r, dict)]