import os
import json
from pathlib import Path

class Config:
    VERSION = "Phoenix Ultra Pro v3.0"
    DEVELOPER = "Phoenix Security Labs"
    
    # Paths
    BASE_DIR = Path(__file__).parent
    SESSION_DIR = BASE_DIR / "sessions"
    LOG_DIR = BASE_DIR / "logs"
    REPORT_DIR = BASE_DIR / "reports"
    
    # Encryption
    ENCRYPTION_KEY = os.urandom(32).hex()
    SALT = os.urandom(16).hex()
    
    # Proxy Configuration (Premium Residential)
    PROXY_POOL = {
        "enabled": True,
        "type": "residential",  # residential, datacenter, mobile
        "rotation": "per_request",
        "countries": ["US", "GB", "DE", "FR", "IN", "PK", "AE", "SA", "SG", "BR"],
        "max_sessions_per_ip": 1,
        "retry_on_fail": 3
    }
    
    # Anti-Detection
    ANTI_DETECTION = {
        "headless": False,
        "disable_webgl": True,
        "spoof_fingerprint": True,
        "random_user_agent": True,
        "random_viewport": True,
        "human_delay_min_ms": 200,
        "human_delay_max_ms": 1500,
        "mouse_movement_simulate": True,
        "tab_switching_simulate": True
    }
    
    # WhatsApp Settings
    WHATSAPP = {
        "max_sessions": 50,
        "session_timeout_min": 30,
        "auto_reconnect": True,
        "message_delay_ms": (3000, 8000),
        "max_messages_per_hour": 50
    }
    
    # Ban Settings
    BAN = {
        "permanent_min_accounts": 25,
        "permanent_max_accounts": 100,
        "temporary_min_accounts": 5,
        "temporary_max_accounts": 20,
        "ban_verification_retries": 5,
        "unban_methods": ["appeal", "recovery", "token_reset", "clone_merge", "api_bypass"]
    }
    
    # API Keys (User will configure)
    API_KEYS = {
        "proxy_service": "",
        "sms_verification": "",
        "captcha_solver": ""
    }
    
    @classmethod
    def load(cls):
        config_file = cls.BASE_DIR / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                data = json.load(f)
                for key, value in data.items():
                    setattr(cls, key, value)
        return cls

config = Config.load()