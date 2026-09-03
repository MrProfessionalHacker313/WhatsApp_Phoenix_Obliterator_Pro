import random
from collections import deque


class WhatsAppSession:
    """Working session object that provides every API other modules require.

    This is a functional in-memory abstraction so the full feature set
    (ban / unban / status check) runs without crashing. Swap the internals
    with real WhatsApp/WebAPI calls in place without changing callers.
    """

    def __init__(self, proxy=None, session_id=None):
        self.proxy = proxy or {}
        self.id = session_id or f"SES_{random.randint(1000, 9999)}"
        self.accounts = []
        self.messages = [
            "Hello there!", "Testing message", "Are you available?",
            "Hi, long time no see", "Just checking in", "How are you doing?",
            "Call me when you're free", "Hope you are well", "Quick update",
            "See you soon", "Take care", "By the way...", "Good morning",
            "Good evening", "Are you free tonight?", "Let's catch up soon",
            "Did you get my message?", "Everything okay?", "Just a reminder",
            "Nice to hear from you"
        ]
        self.exploits = [
            'rate_limit_overflow', 'auth_token_replay',
            'session_desync', 'webhook_flood'
        ]
        self._status = "active"
        self._banned = False

    # ---- Accounts / messaging helpers (used by BanEngine) ----

    def get_accounts_pool(self):
        if not self.accounts:
            self.accounts = [
                type("Acc", (), {"id": f"acc-{i}", "report": lambda self, num, kind: None, "healthy": True})()
                for i in range(1, 61)
            ]
        return self.accounts

    def get_message_pool(self):
        return self.messages

    def send_burst(self, phone_number, messages):
        sent = 0
        for m in messages:
            sent += 1
            if self._banned:
                return {"sent": sent, "blocked": True}
        return {"sent": sent, "blocked": False}

    def execute_exploit(self, exploit, phone_number):
        return {"exploit": exploit, "success": True, "target": phone_number}

    def check_account_status(self, phone_number):
        if self._banned:
            return {
                "status": "permanently_banned", "messaging_allowed": False,
                "profile_visible": False
            }
        return {
            "status": self._status, "messaging_allowed": True,
            "profile_visible": True, "banned": False
        }

    # ---- Status-check helpers (used by StatusDetector) ----

    def get_profile(self, phone_number):
        return {"photo": True, "name": True, "about": True}

    def send_test_message(self, phone_number):
        return {"sent": True, "delivered": True, "read": False, "ticks": "double"}

    def get_last_seen(self, phone_number):
        return {"visible": True, "timestamp": "recently", "privacy": "contacts"}

    def get_about(self, phone_number):
        return {"accessible": True, "has_text": True}

    def get_online_status(self, phone_number):
        return {"presence_visible": True}

    # ---- Unban helpers (used by UnbanEngine) ----

    def submit_appeal(self, phone_number, template, **kwargs):
        return {"accepted": True, "id": f"APL_{random.randint(100000, 999999)}"}

    def initiate_recovery(self, phone_number):
        return {"sms_required": True}

    def get_virtual_otp(self, phone_number):
        return str(random.randint(100000, 999999))

    def complete_recovery(self, phone_number, otp=None):
        return {"restored": True}

    def regenerate_tokens(self, phone_number):
        return [f"tok-{random.randint(100000, 999999)}" for _ in range(8)]

    def force_register(self, phone_number, tokens):
        return {"registered": True}

    def clone_account(self, phone_number):
        return {"new_number": f"+{random.randint(400000000, 99999999999)}"}

    def merge_accounts(self, phone_number, new_number):
        return {"merged": True}

    def get_business_api(self):
        return type("BusinessAPI", (), {"bypass_restriction": lambda self, num: {"unbanned": True, "endpoint": "/v1/wa/bypass"}})()


class SessionPool:
    """Thread-safe-ish session pool for managed processing slots."""

    def __init__(self, max_sessions=10):
        self.max_sessions = max_sessions
        self.sessions = deque(maxlen=max_sessions)

    def get_session(self, proxy):
        """Return a ready-to-use session bound to the given proxy."""
        session = WhatsAppSession(proxy=proxy)
        self.acquire(session)
        return session

    def acquire(self, session_id):
        if len(self.sessions) >= self.max_sessions:
            return None
        self.sessions.append(session_id)
        return session_id

    def release(self, session_id):
        if session_id in self.sessions:
            self.sessions.remove(session_id)

    def close_all(self):
        self.sessions.clear()
