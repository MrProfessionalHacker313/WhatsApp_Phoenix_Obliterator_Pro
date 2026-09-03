"""
PHOENIX EAGLE — PAYMENT CONFIGURATION
=====================================
Central configuration for the payment & licensing subsystem.

All sensitive values are read from environment variables so the code
holds no secrets. A .env file / shell export can provide them in
production.

Plans
-----
BASIC  :  $29 / 1 month
PRO    :  $99 / 6 months
ELITE  :  $299 / 1 year + lifetime updates
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# License tier definitions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Plan:
    """A purchasable / licensable plan."""

    key: str
    name: str
    display_name: str
    price_cents: int          # price in US cents (Stripe convention)
    price_usd: str            # human readable e.g. "$29"
    duration_days: int        # license validity in days
    recurring: bool           # True if sold as a monthly/yearly subscription
    lifetime_updates: bool    # Elite perk
    perks: tuple = field(default_factory=tuple)


PLAN_BASIC = Plan(
    key="basic",
    name="BASIC",
    display_name="Basic",
    price_cents=2900,
    price_usd="$29",
    duration_days=30,          # 1 month
    recurring=True,
    lifetime_updates=False,
    perks=("1 Month Access", "Core Features", "Email Support"),
)

PLAN_PRO = Plan(
    key="pro",
    name="PRO",
    display_name="Pro",
    price_cents=9900,
    price_usd="$99",
    duration_days=180,         # 6 months
    recurring=True,
    lifetime_updates=False,
    perks=("6 Months Access", "Advanced Features", "Priority Support"),
)

PLAN_ELITE = Plan(
    key="elite",
    name="ELITE",
    display_name="Elite",
    price_cents=29900,
    price_usd="$299",
    duration_days=365,         # 1 year
    recurring=False,
    lifetime_updates=True,
    perks=("1 Year Access", "Lifetime Updates", "Dedicated Concierge"),
)

# Lookup helpers
PLANS = {p.key: p for p in (PLAN_BASIC, PLAN_PRO, PLAN_ELITE)}


# ---------------------------------------------------------------------------
# License statuses + tier enums (shared across modules)

# ---------------------------------------------------------------------------
# Machine ID / storage paths
# ---------------------------------------------------------------------------
def _home_dir() -> str:
    return os.path.expanduser("~")


LICENSE_FILE = os.path.join(_home_dir(), ".phoenix_license")
DEMO_STATE_FILE = os.path.join(_home_dir(), ".phoenix_demo_state")
LICENSE_PUBKEY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "license_public.pem"
)
RSA_KEYSET_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "keyset"
)
RSA_PRIVATE_KEY_FILE = os.path.join(RSA_KEYSET_DIR, "license_private.pem")
RSA_PUBLIC_KEY_FILE = os.path.join(RSA_KEYSET_DIR, "license_public.pem")


# ---------------------------------------------------------------------------
# Environment-driven settings
# ---------------------------------------------------------------------------
def get_setting(name: str, default: str = "") -> str:
    """Read a configuration value from the environment with fallback."""
    return os.environ.get(name, default).strip()


def get_bool_setting(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def get_int_setting(name: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


class PaymentConfig:
    """Runtime accessor for all payment-related environment settings."""

    # ------------------------------------------------------------- Stripe
    @property
    def stripe_secret_key(self) -> str:
        return get_setting("STRIPE_SECRET_KEY")

    @property
    def stripe_publishable_key(self) -> str:
        return get_setting("STRIPE_PUBLISHABLE_KEY")

    @property
    def stripe_webhook_secret(self) -> str:
        return get_setting("STRIPE_WEBHOOK_SECRET")

    @property
    def stripe_api_version(self) -> str:
        return get_setting("STRIPE_API_VERSION", "2024-06-20")

    # ------------------------------------------------------------- PayPal
    @property
    def paypal_client_id(self) -> str:
        return get_setting("PAYPAL_CLIENT_ID")

    @property
    def paypal_client_secret(self) -> str:
        return get_setting("PAYPAL_CLIENT_SECRET")

    @property
    def paypal_mode(self) -> str:
        # "sandbox" or "live"
        return get_setting("PAYPAL_MODE", "sandbox")

    @property
    def paypal_ipn_verify_url(self) -> str:
        base = "https://ipnpb.sandbox.paypal.com" if self.paypal_mode == "sandbox" \
            else "https://ipnpb.paypal.com"
        return base + "/cgi-bin/webscr"

    @property
    def paypal_api_base(self) -> str:
        return "https://api-m.sandbox.paypal.com" if self.paypal_mode == "sandbox" \
            else "https://api-m.paypal.com"

    # ------------------------------------------------------------- Generic
    @property
    def base_url(self) -> str:
        # Public base URL of the payment server (used for redirects)
        return get_setting("PAYMENT_BASE_URL", "http://127.0.0.1:8787").rstrip("/")

    @property
    def server_host(self) -> str:
        return get_setting("PAYMENT_SERVER_HOST", "127.0.0.1")

    @property
    def server_port(self) -> int:
        return get_int_setting("PAYMENT_SERVER_PORT", 8787)

    @property
    def email_from(self) -> str:
        return get_setting("EMAIL_FROM", "no-reply@phoenixobliterator.internal")

    @property
    def email_enabled(self) -> bool:
        return get_bool_setting("EMAIL_ENABLED", False)

    @property
    def allow_online_validation(self) -> bool:
        return get_bool_setting("ALLOW_ONLINE_LICENSE_VALIDATION", True)


CONFIG = PaymentConfig()

# ---------------------------------------------------------------------------
class LicenseStatus:
    ACTIVE = "active"
    EXPIRED = "expired"
    TRIAL = "trial"
    INVALID = "invalid"
    HARDWARE_MISMATCH = "hardware_mismatch"
    DEMO = "demo"


class LicenseTier:
    BASIC = "basic"
    PRO = "pro"
    ELITE = "elite"
    TRIAL = "trial"