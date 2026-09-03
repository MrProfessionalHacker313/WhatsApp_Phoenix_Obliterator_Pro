"""
PHOENIX EAGLE — PAYMENT & LICENSING PACKAGE
============================================
Production-ready payment gateway (Stripe + PayPal) and hardware-locked
license management. All modules are importable standalone so the CLI,
the Flask payment server, and tests can share them.

Modules
-------
- license_manager  : RSA-2048 license generation / validation / tiers
- stripe_gateway   : Stripe checkout + webhooks + subscriptions
- paypal_gateway   : PayPal REST orders + IPN
- payment_server   : Flask web server bridging the CLI and the gateways
- config           : centralised, env-driven configuration

Security principles honoured throughout:
  * No secret keys are hard-coded -> read from environment or config.build.
  * License signatures are verified offline with an embedded public key.
  * Webhooks are signature-checked (Stripe) / IPN-verified (PayPal).
  * License state is stored encrypted at rest (~/.phoenix_license).
"""

from .config import (
    PLANS,
    PLAN_BASIC,
    PLAN_PRO,
    PLAN_ELITE,
    get_setting,
)

from .license_manager import (
    LicenseManager,
    LicenseTier,
    LicenseStatus,
    generate_machine_id,
)

from .stripe_gateway import StripeGateway
from .paypal_gateway import PayPalGateway
from .emailer import send_license_email

__all__ = [
    "PLANS",
    "PLAN_BASIC",
    "PLAN_PRO",
    "PLAN_ELITE",
    "get_setting",
    "LicenseManager",
    "LicenseTier",
    "LicenseStatus",
    "generate_machine_id",
    "StripeGateway",
    "PayPalGateway",
    "send_license_email",
]

__version__ = "1.0.0"