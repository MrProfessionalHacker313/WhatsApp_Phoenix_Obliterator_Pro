import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from colorama import Fore

from .ban_validator import BanValidator


class TempBanManager:
    """
    Temporary ban lifecycle manager.
    Tracks temp bans in evidence/temp_bans.json, auto-expires stale entries,
    and surfaces active / expired records.
    """

    DEFAULT_EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "evidence"
    BAN_LOG_FILE = "temp_bans.json"
    CLEANUP_INTERVAL = 100

    def __init__(self, evidence_dir=None):
        self.evidence_dir = Path(evidence_dir) if evidence_dir else self.DEFAULT_EVIDENCE_DIR
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.ban_file = self.evidence_dir / self.BAN_LOG_FILE
        self._records = self._load_records()
        self._cleanup_counter = 0
        self.validator = BanValidator(evidence_dir=self.evidence_dir)

    def _load_records(self):
        if self.ban_file.exists():
            with open(self.ban_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"temp_bans": {}}

    def _save_records(self):
        with open(self.ban_file, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2, ensure_ascii=False)

    def apply_temp_ban(self, phone_number, duration_hours, reason="spam_activity"):
        validation = self.validator.validate(phone_number, ban_type="temporary")
        if not validation["valid"]:
            return {"success": False, "error": "Validation failed", "reasons": validation["reasons"]}

        phone_number = self.validator._normalize(phone_number)
        now = datetime.utcnow()
        expires_at = (now + timedelta(hours=duration_hours)).isoformat()

        record = {
            "phone_number": phone_number,
            "reason": reason,
            "applied_at": now.isoformat(),
            "expires_at": expires_at,
            "duration_hours": duration_hours,
            "status": "active",
        }

        self._records["temp_bans"][phone_number] = record
        self._save_records()

        self.validator.register_ban_attempt(phone_number, "temporary", success=True)

        print(f"{Fore.GREEN}[TEMP_BAN] Applied {duration_hours}h temp ban on {phone_number}")
        return {"success": True, "record": record}

    def lift_temp_ban(self, phone_number):
        phone_number = self.validator._normalize(phone_number)
        record = self._records.get("temp_bans", {}).get(phone_number)

        if not record:
            return {"success": False, "error": "No active temp ban found"}

        if record.get("status") == "expired":
            return {"success": False, "error": "Ban already expired"}

        record["status"] = "lifted"
        record["lifted_at"] = datetime.utcnow().isoformat()
        self._save_records()

        print(f"{Fore.YELLOW}[TEMP_BAN] Lifted temp ban on {phone_number}")
        return {"success": True, "record": record}

    def is_temp_banned(self, phone_number):
        self._maybe_cleanup()
        phone_number = self.validator._normalize(phone_number)
        record = self._records.get("temp_bans", {}).get(phone_number)

        if not record:
            return {"banned": False}

        status = record.get("status")
        if status == "lifted":
            return {"banned": False, "reason": "lifted"}

        if status == "expired":
            return {"banned": False, "reason": "expired"}

        expires_at = datetime.fromisoformat(record["expires_at"])
        if datetime.utcnow() >= expires_at:
            record["status"] = "expired"
            record["expired_at"] = datetime.utcnow().isoformat()
            self._save_records()
            return {"banned": False, "reason": "expired"}

        remaining = expires_at - datetime.utcnow()
        return {
            "banned": True,
            "reason": record.get("reason"),
            "expires_at": record["expires_at"],
            "remaining_seconds": int(remaining.total_seconds()),
            "duration_hours": record.get("duration_hours"),
        }

    def get_active_temp_bans(self):
        self._maybe_cleanup()
        active = []
        for phone_number, record in self._records.get("temp_bans", {}).items():
            if record.get("status") != "active":
                continue
            expires_at = datetime.fromisoformat(record["expires_at"])
            if datetime.utcnow() >= expires_at:
                record["status"] = "expired"
                record["expired_at"] = datetime.utcnow().isoformat()
                continue
            active.append(record)
        if any(r.get("status") == "expired" for r in self._records.get("temp_bans", {}).values()):
            self._save_records()
        return active

    def get_history(self, phone_number=None):
        self._maybe_cleanup()
        bans = self._records.get("temp_bans", {})
        if phone_number:
            phone_number = self.validator._normalize(phone_number)
            return bans.get(phone_number)
        return list(bans.values())

    def _maybe_cleanup(self):
        self._cleanup_counter += 1
        if self._cleanup_counter >= self.CLEANUP_INTERVAL:
            self._cleanup_counter = 0
            self._cleanup_expired()

    def _cleanup_expired(self):
        now = datetime.utcnow()
        changed = False
        for record in self._records.get("temp_bans", {}).values():
            if record.get("status") != "active":
                continue
            expires_at = datetime.fromisoformat(record["expires_at"])
            if now >= expires_at:
                record["status"] = "expired"
                record["expired_at"] = now.isoformat()
                changed = True
        if changed:
            self._save_records()
