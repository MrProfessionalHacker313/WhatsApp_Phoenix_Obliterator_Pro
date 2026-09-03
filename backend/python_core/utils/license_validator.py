"""
PHOENIX EAGLE — LICENSE VALIDATOR
=================================
Reads the encrypted license at ``~/.phoenix_license`` and exposes a guard that
must run before EVERY operation.

Behaviour
---------
* Valid, unexpired, hardware-matched license -> full access.
* No license (or expired/invalid) -> DEMO MODE with a limited number of
  operations (default 3), after which operations are refused until a valid
  license is activated.

The result of the last check is cached so the CLI does not re-decode + verify
the RSA signature on every keystroke, but the guard still honours expiry.
"""

from __future__ import annotations

import os
import logging

from payment.config import (DEMO_STATE_FILE, LICENSE_FILE, LicenseStatus)
from payment.license_manager import LicenseManager

try:
    from payment.owner_access import is_owner
    _OWNER_AVAILABLE = True
except Exception:
    _OWNER_AVAILABLE = False

logger = logging.getLogger("phoenix.utils.license_validator")

# Number of operations allowed in demo mode before a license is required.
DEMO_MAX_OPERATIONS = 3

# Reason string surfaced to the user interface.
DEMO_BANNER = "⚠️  DEMO MODE - Only 3 operations allowed"


class _Validator:
    def __init__(self):
        self._manager = LicenseManager()
        self._cached_load: dict | None = None
        self._loaded = False

    # ------------------------------------------------------------- state
    def _demo_state(self) -> dict:
        """Read the persistent demo-operation count."""
        try:
            if os.path.exists(DEMO_STATE_FILE):
                with open(DEMO_STATE_FILE, "r", encoding="utf-8") as fh:
                    return {"count": int(fh.read().strip() or "0")}
        except Exception:
            pass
        return {"count": 0}

    def _save_demo_state(self, count: int) -> None:
        try:
            with open(DEMO_STATE_FILE, "w", encoding="utf-8") as fh:
                fh.write(str(count))
        except Exception as exc:
            logger.warning("Could not persist demo state: %s", exc)

    # ------------------------------------------------------------- loading
    def _payload(self) -> dict | None:
        """Return the decoded stored license payload (cached)."""
        if self._loaded:
            return self._cached_load
        self._loaded = True
        self._cached_load = self._manager.load_stored()
        return self._cached_load

    # ------------------------------------------------------------- status
    def license_status(self) -> dict:
        """
        Return the current license status:
            {status, valid, tier, license_key, expires_at, remaining_days,
             demo_operations_used, demo_operations_left, reason}
        """
        if _OWNER_AVAILABLE and is_owner():
            return {
                "status": "owner",
                "valid": True,
                "tier": "owner",
                "license_key": None,
                "expires_at": None,
                "remaining_days": None,
                "demo_operations_used": 0,
                "demo_operations_left": None,
                "reason": "Owner access — unlimited",
            }

        payload = self._payload()
        if payload is None:
            state = self._demo_state()
            return {
                "status": LicenseStatus.DEMO,
                "valid": False,
                "tier": "demo",
                "license_key": None,
                "expires_at": None,
                "remaining_days": None,
                "demo_operations_used": state["count"],
                "demo_operations_left": max(0, DEMO_MAX_OPERATIONS - state["count"]),
                "reason": "No valid license found — demo mode",
            }

        result = self._manager.validate(payload, force_offline=True)
        # If the stored license fails validation, fall back to demo.
        if not result["valid"]:
            state = self._demo_state()
            return {
                "status": result["status"],
                "valid": False,
                "tier": result["tier"],
                "license_key": None,
                "expires_at": result["expires_at"],
                "remaining_days": result["remaining_days"],
                "demo_operations_used": state["count"],
                "demo_operations_left": max(0, DEMO_MAX_OPERATIONS - state["count"]),
                "reason": result["reason"],
            }

        return {
            "status": LicenseStatus.ACTIVE,
            "valid": True,
            "tier": result["tier"],
            "license_key": self._key_from(payload),
            "expires_at": result["expires_at"],
            "remaining_days": result["remaining_days"],
            "demo_operations_used": 0,
            "demo_operations_left": None,
            "reason": "Active",
        }

    @staticmethod
    def _key_from(payload: dict) -> str:
        try:
            return LicenseManager().human_license_key(payload)
        except Exception:
            return ""

    @property
    def is_full(self) -> bool:
        return self.license_status()["valid"]
# ------------------------------------------------------------- guard
    def check(self) -> bool:
        """
        Guard to call before EVERY operation.

        Returns True if the operation may proceed (full access), or False if
        the demo-operation budget is exhausted and a license is required.
        """
        if _OWNER_AVAILABLE and is_owner():
            return True

        status = self.license_status()
        if status["valid"]:
            return True  # full access

        state = self._demo_state()
        used = state["count"]
        if used < DEMO_MAX_OPERATIONS:
            # Grant one more demo operation.
            self._save_demo_state(used + 1)
            return True

        return False

    def reset_demo(self) -> None:
        """Wipe the demo counter (e.g. after successful activation)."""
        if os.path.exists(DEMO_STATE_FILE):
            try:
                os.remove(DEMO_STATE_FILE)
            except Exception:
                pass

    def activate(self, license_key: str) -> dict:
        """Activate + persist a license, resetting the demo budget on success."""
        result = self._manager.activate(license_key, persist=True)
        if result["valid"]:
            self._loaded = False
            self._cached_load = None
            self.reset_demo()
        return result


# ---------------------------------------------------------------------------
# Module-level singleton (the CLI imports this once).
# ---------------------------------------------------------------------------
_validator = _Validator()


def get_validator() -> _Validator:
    return _validator


def require_license() -> bool:
    """Thin wrapper used by the CLI's operation dispatcher."""
    return _validator.check()


def license_status() -> dict:
    return _validator.license_status()


def is_full_access() -> bool:
    return _validator.is_full