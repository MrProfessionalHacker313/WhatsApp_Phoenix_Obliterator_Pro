import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from colorama import Fore


class BanValidator:
    """
    Pre-ban validation engine.
    Checks phone number eligibility before any ban operation.
    """

    BAN_COOLDOWN_HOURS = 24
    MAX_DAILY_BANS = 50
    MAX_RECENT_BANS = 10
    RECENT_WINDOW_MINUTES = 60

    def __init__(self, evidence_dir=None):
        self.evidence_dir = Path(evidence_dir) if evidence_dir else Path(__file__).resolve().parents[2] / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.ban_log_file = self.evidence_dir / "ban_records.json"
        self._records = self._load_records()

    def _load_records(self):
        if self.ban_log_file.exists():
            with open(self.ban_log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"banned_numbers": {}, "daily_stats": {}}

    def _save_records(self):
        with open(self.ban_log_file, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2, ensure_ascii=False)

    def validate(self, phone_number, ban_type="permanent"):
        phone_number = self._normalize(phone_number)

        checks = {
            "format_valid": self._check_format(phone_number),
            "not_already_banned": self._check_not_already_banned(phone_number),
            "not_in_cooldown": self._check_cooldown(phone_number),
            "daily_limit_ok": self._check_daily_limit(),
            "recent_attempts_ok": self._check_recent_attempts(phone_number),
        }

        passed = all(checks.values())
        reasons = [k for k, v in checks.items() if not v]

        result = {
            "valid": passed,
            "phone_number": phone_number,
            "ban_type": ban_type,
            "checks": checks,
            "reasons": reasons,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if passed:
            print(f"{Fore.GREEN}[VALIDATOR] Ban approved for {phone_number}")
        else:
            print(f"{Fore.RED}[VALIDATOR] Ban rejected for {phone_number}: {', '.join(reasons)}")

        return result

    def _normalize(self, phone_number):
        return re.sub(r"[^\d]", "", str(phone_number))

    def _check_format(self, phone_number):
        return bool(re.fullmatch(r"\d{10,15}", phone_number))

    def _check_not_already_banned(self, phone_number):
        banned = self._records.get("banned_numbers", {}).get(phone_number)
        if not banned:
            return True
        status = banned.get("status")
        return status not in ("active", "pending")

    def _check_cooldown(self, phone_number):
        banned = self._records.get("banned_numbers", {}).get(phone_number)
        if not banned:
            return True
        last_attempt = banned.get("last_attempt")
        if not last_attempt:
            return True
        last_time = datetime.fromisoformat(last_attempt)
        return datetime.utcnow() - last_time > timedelta(hours=self.BAN_COOLDOWN_HOURS)

    def _check_daily_limit(self):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        stats = self._records.get("daily_stats", {})
        used = stats.get(today, 0)
        return used < self.MAX_DAILY_BANS

    def _check_recent_attempts(self, phone_number):
        cutoff = datetime.utcnow() - timedelta(minutes=self.RECENT_WINDOW_MINUTES)
        banned = self._records.get("banned_numbers", {}).get(phone_number)
        if not banned:
            return True
        last_attempt = banned.get("last_attempt")
        if not last_attempt:
            return True
        return datetime.fromisoformat(last_attempt) < cutoff

    def register_ban_attempt(self, phone_number, ban_type, success):
        phone_number = self._normalize(phone_number)
        today = datetime.utcnow().strftime("%Y-%m-%d")

        if phone_number not in self._records["banned_numbers"]:
            self._records["banned_numbers"][phone_number] = {}

        self._records["banned_numbers"][phone_number].update({
            "last_attempt": datetime.utcnow().isoformat(),
            "last_ban_type": ban_type,
            "status": "active" if success else "failed",
        })

        stats = self._records.setdefault("daily_stats", {})
        stats[today] = stats.get(today, 0) + 1

        self._save_records()

    def get_ban_history(self, phone_number):
        phone_number = self._normalize(phone_number)
        return self._records.get("banned_numbers", {}).get(phone_number)
