"""
PHOENIX EAGLE — LICENSE EMAILER
===============================
Sends the issued license key to the customer by email after a successful
payment (the final step of the payment flow).

Configuration (environment variables):
    EMAIL_ENABLED         "1"/"true" to turn on
    SMTP_HOST             e.g. smtp.example.com
    SMTP_PORT             587 (default)
    SMTP_USER             username
    SMTP_PASS             password
    EMAIL_FROM            sender address
    EMAIL_USE_TLS         "1"/"true" (default True for STARTTLS)

If email is not configured the function writes the license to a local file
(payment/licenses_email_log.json) so nothing is lost, and returns False.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import CONFIG

logger = logging.getLogger("phoenix.payment.emailer")

EMAIL_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "licenses_email_log.json")


def _smtp_settings() -> dict:
    from .config import get_setting
    return {
        "host": get_setting("SMTP_HOST"),
        "port": int(get_setting("SMTP_PORT", "587") or 587),
        "user": get_setting("SMTP_USER"),
        "password": get_setting("SMTP_PASS"),
        "use_tls": os.environ.get("EMAIL_USE_TLS", "1").lower() in ("1", "true"),
    }


def send_license_email(to_email: str, license_key: str, plan_name: str,
                       tier: str, expires_at: str) -> bool:
    """
    Email the license key to the customer. Returns True on success.

    Falls back to persisting the details locally when email is disabled.
    """
    if not to_email:
        logger.info("No customer email — license logged locally only.")
        _log_license(to_email, license_key, plan_name, tier, expires_at)
        return False

    if not CONFIG.email_enabled:
        _log_license(to_email, license_key, plan_name, tier, expires_at)
        logger.info("Email disabled — license logged to %s", EMAIL_LOG)
        return False

    subs = _smtp_settings()
    if not subs["host"] or not subs["user"] or not subs["password"]:
        logger.warning("SMTP not fully configured — license logged locally.")
        _log_license(to_email, license_key, plan_name, tier, expires_at)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Phoenix Eagle License Key"
        msg["From"] = CONFIG.email_from
        msg["To"] = to_email

        text = (
            f"Thank you for your purchase of the {plan_name} plan.\n\n"
            f"Your Phoenix Eagle license key is:\n\n    {license_key}\n\n"
            f"Tier: {tier}\n"
            f"Expires: {expires_at}\n\n"
            f"Activate it in the tool via the PAYMENT / LICENSE menu.\n\n"
            f"The key is locked to this machine's hardware identifier.\n\n"
            f"— Phoenix Security Labs\n"
        )
        msg.attach(MIMEText(text, "plain"))

        if subs["use_tls"]:
            server = smtplib.SMTP(subs["host"], subs["port"], timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP(subs["host"], subs["port"], timeout=15)
        server.login(subs["user"], subs["password"])
        server.sendmail(CONFIG.email_from, [to_email], msg.as_string())
        server.quit()
        logger.info("License emailed to %s", to_email)
        _log_license(to_email, license_key, plan_name, tier, expires_at)
        return True

    except Exception as exc:
        logger.error("Failed to email license: %s", exc)
        _log_license(to_email, license_key, plan_name, tier, expires_at)
        return False


def _log_license(to_email, license_key, plan_name, tier, expires_at):
    """Record issued licenses so they can never be lost, even if email fails."""
    try:
        data = {}
        if os.path.exists(EMAIL_LOG):
            with open(EMAIL_LOG, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        data[to_email or "no-email"] = {
            "license_key": license_key,
            "plan": plan_name,
            "tier": tier,
            "expires_at": expires_at,
            "issued": __import__("datetime").datetime.now().isoformat(),
        }
        with open(EMAIL_LOG, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception as exc:
        logger.warning("Could not log license to file: %s", exc)