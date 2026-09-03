"""
PHOENIX EAGLE — OWNER ACCESS SYSTEM
====================================
Master key / admin access layer that sits above the normal licensing system.
All owner actions are audited and machine-locked.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone

from .config import PLANS
from .license_manager import LicenseManager, LicenseTier, generate_machine_id

logger = logging.getLogger("phoenix.owner")

# ---------------------------------------------------------------------------
# Master key (SHA-256 hash — never plaintext in code)
# ---------------------------------------------------------------------------
_MASTER_KEY_HASH = hashlib.sha256(
    "OWNER-PHOENIX-XMASTER-ETERNAL-001".encode("utf-8")
).hexdigest()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_OWNER_FILE = os.path.expanduser("~/.phoenix_owner")
_GENERATED_KEYS_FILE = os.path.expanduser("~/.phoenix_generated_keys.json")
_OWNER_AUDIT_LOG = os.path.expanduser("~/.phoenix_owner_audit.log")
_MAX_GENERATED_KEYS = 500


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------
def _log_audit(action: str, details: str = "") -> None:
    try:
        ts = datetime.now(timezone.utc).isoformat()
        mid = generate_machine_id()
        entry = f"{ts} | {mid[:16]}... | {action} | {details}\n"
        with open(_OWNER_AUDIT_LOG, "a", encoding="utf-8") as fh:
            fh.write(entry)
    except Exception as exc:
        logger.warning("Owner audit log failed: %s", exc)


# ---------------------------------------------------------------------------
# OwnerAccess
# ---------------------------------------------------------------------------
class OwnerAccess:
    """Owner / admin access controller."""

    def __init__(self) -> None:
        self._machine_id: str = generate_machine_id()
        self._generated_keys: list[dict] = self._load_generated_keys()

    # ----------------------------------------------------------- persistence
    def _load_generated_keys(self) -> list[dict]:
        try:
            if os.path.exists(_GENERATED_KEYS_FILE):
                with open(_GENERATED_KEYS_FILE, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, list):
                        return data
        except Exception:
            pass
        return []

    def _save_generated_keys(self) -> None:
        try:
            with open(_GENERATED_KEYS_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._generated_keys, fh, indent=2)
        except Exception as exc:
            logger.warning("Could not persist generated keys: %s", exc)

    # ----------------------------------------------------------- status
    def is_active(self) -> bool:
        """Return True if owner mode is active on THIS machine."""
        if not os.path.exists(_OWNER_FILE):
            return False
        try:
            with open(_OWNER_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("machine_id") != self._machine_id:
                return False
            return bool(data.get("active"))
        except Exception:
            return False

    def status(self) -> dict:
        """Return owner status dict."""
        return {
            "active": self.is_active(),
            "machine_id": self._machine_id[:16] + "...",
            "keys_generated": len(self._generated_keys),
            "max_keys": _MAX_GENERATED_KEYS,
        }

    def get_badge(self) -> str:
        """Return owner badge for UI rendering."""
        return "🦅 [OWNER] 🦅"

    # ----------------------------------------------------------- activate
    def activate(self, master_key: str) -> dict:
        """Activate owner mode. Returns {success: bool, reason: str}."""
        input_hash = hashlib.sha256(master_key.encode("utf-8")).hexdigest()
        if input_hash != _MASTER_KEY_HASH:
            _log_audit("ACTIVATE_FAILED", "Invalid master key")
            return {"success": False, "reason": "Invalid master key"}

        if self.is_active():
            return {"success": False, "reason": "Owner mode already active on this machine"}

        payload = {
            "active": True,
            "machine_id": self._machine_id,
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(_OWNER_FILE, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            _log_audit("ACTIVATE", "Owner mode activated")
            return {"success": True}
        except Exception as exc:
            return {"success": False, "reason": str(exc)}

    # ----------------------------------------------------------- deactivate
    def deactivate(self) -> dict:
        """Deactivate owner mode. Returns {success: bool, reason: str}."""
        if not self.is_active():
            return {"success": False, "reason": "Owner mode is not active"}

        try:
            if os.path.exists(_OWNER_FILE):
                os.remove(_OWNER_FILE)
            _log_audit("DEACTIVATE", "Owner mode deactivated")
            return {"success": True}
        except Exception as exc:
            return {"success": False, "reason": str(exc)}

    # ----------------------------------------------------------- genkey
    def genkey(self, tier: str, duration: int | str, target_machine_id: str = "") -> dict:
        """
        Generate a free license key.

        Args:
            tier: basic / pro / elite / trial
            duration: days (int) or 'lifetime' / 'forever' / 'max'
            target_machine_id: optional machine ID to bind the key to.
                               If empty, binds to the current machine.

        Returns:
            {success, key, tier, days, reason}
        """
        if not self.is_active():
            return {"success": False, "reason": "Owner mode not active"}

        tier_lower = tier.lower()
        if tier_lower not in (LicenseTier.BASIC, LicenseTier.PRO, LicenseTier.ELITE, LicenseTier.TRIAL):
            return {
                "success": False,
                "reason": f"Invalid tier '{tier}'. Use: basic, pro, elite, trial",
            }

        # Resolve duration
        if isinstance(duration, str):
            if duration.lower() in ("lifetime", "forever", "max", "eternal"):
                days = 3650
            else:
                try:
                    days = int(duration)
                except ValueError:
                    return {"success": False, "reason": "Duration must be a number or 'lifetime'"}
        else:
            days = int(duration)

        if days <= 0 or days > 3650:
            return {"success": False, "reason": "Duration must be between 1 and 3650 days"}

        # Enforce key limit
        if len(self._generated_keys) >= _MAX_GENERATED_KEYS:
            return {"success": False, "reason": f"Maximum {_MAX_GENERATED_KEYS} keys already generated"}

        # Determine machine binding
        machine_id = target_machine_id.strip() if target_machine_id else self._machine_id

        try:
            manager = LicenseManager()
            payload = manager.generate_license(
                tier=tier_lower,
                machine_id=machine_id,
                duration_days=days,
                customer_email="owner-generated",
            )
            license_key = manager.human_license_key(payload)

            entry = {
                "key": license_key,
                "tier": tier_lower,
                "days": days,
                "target_machine": machine_id[:16] + "..." if machine_id else "current",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "used": False,
            }
            self._generated_keys.append(entry)
            self._save_generated_keys()
            _log_audit("GENKEY", f"{tier_lower} | {days}d | {machine_id[:16]}...")
            return {"success": True, "key": license_key, "tier": tier_lower, "days": days}
        except Exception as exc:
            logger.error("Key generation failed: %s", exc)
            return {"success": False, "reason": str(exc)}

    # ----------------------------------------------------------- list keys
    def list_keys(self) -> list[dict]:
        """Return all generated keys."""
        return list(self._generated_keys)


# ---------------------------------------------------------------------------
# Singleton + module-level helpers
# ---------------------------------------------------------------------------
_owner = OwnerAccess()


def get_owner() -> OwnerAccess:
    return _owner


def is_owner() -> bool:
    return _owner.is_active()


def owner_badge() -> str:
    return _owner.get_badge() if is_owner() else ""
