import os
import json
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger("phoenix.cache")

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

_redis_client = None
if REDIS_AVAILABLE:
    try:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            health_check_interval=30
        )
        _redis_client.ping()
        logger.info("Redis cache connected")
    except Exception as e:
        logger.warning("Redis not available: %s", e)
        _redis_client = None


def get_redis() -> Optional["redis.Redis"]:
    return _redis_client


class NumberCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds

    def _key(self, phone: str) -> str:
        return f"phoenix:number:{phone}"

    def get(self, phone: str) -> Optional[Dict[str, Any]]:
        client = get_redis()
        if not client:
            return None
        try:
            raw = client.get(self._key(phone))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, phone: str, value: Dict[str, Any], ttl: Optional[int] = None):
        client = get_redis()
        if not client:
            return
        try:
            client.set(self._key(phone), json.dumps(value), ex=ttl or self.ttl)
        except Exception:
            pass

    def delete(self, phone: str):
        client = get_redis()
        if not client:
            return
        try:
            client.delete(self._key(phone))
        except Exception:
            pass

    def clear(self):
        client = get_redis()
        if not client:
            return
        try:
            keys = client.keys("phoenix:number:*")
            if keys:
                client.delete(*keys)
        except Exception:
            pass


class SessionCache:
    def __init__(self, ttl_seconds: int = 1800):
        self.ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"phoenix:session:{session_id}"

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        client = get_redis()
        if not client:
            return None
        try:
            raw = client.get(self._key(session_id))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, session_id: str, value: Dict[str, Any], ttl: Optional[int] = None):
        client = get_redis()
        if not client:
            return
        try:
            client.set(self._key(session_id), json.dumps(value), ex=ttl or self.ttl)
        except Exception:
            pass

    def delete(self, session_id: str):
        client = get_redis()
        if not client:
            return
        try:
            client.delete(self._key(session_id))
        except Exception:
            pass

    def list_active(self) -> List[str]:
        client = get_redis()
        if not client:
            return []
        try:
            keys = client.keys("phoenix:session:*")
            return [k.split(":", 2)[-1] for k in keys]
        except Exception:
            return []


class LicenseCache:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl = ttl_seconds

    def _key(self, license_key: str) -> str:
        return f"phoenix:license:{license_key}"

    def get(self, license_key: str) -> Optional[Dict[str, Any]]:
        client = get_redis()
        if not client:
            return None
        try:
            raw = client.get(self._key(license_key))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, license_key: str, value: Dict[str, Any], ttl: Optional[int] = None):
        client = get_redis()
        if not client:
            return
        try:
            client.set(self._key(license_key), json.dumps(value), ex=ttl or self.ttl)
        except Exception:
            pass

    def delete(self, license_key: str):
        client = get_redis()
        if not client:
            return
        try:
            client.delete(self._key(license_key))
        except Exception:
            pass


class OperationCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds

    def _key(self, operation_id: str) -> str:
        return f"phoenix:operation:{operation_id}"

    def get(self, operation_id: str) -> Optional[Dict[str, Any]]:
        client = get_redis()
        if not client:
            return None
        try:
            raw = client.get(self._key(operation_id))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, operation_id: str, value: Dict[str, Any], ttl: Optional[int] = None):
        client = get_redis()
        if not client:
            return
        try:
            client.set(self._key(operation_id), json.dumps(value), ex=ttl or self.ttl)
        except Exception:
            pass

    def delete(self, operation_id: str):
        client = get_redis()
        if not client:
            return
        try:
            client.delete(self._key(operation_id))
        except Exception:
            pass


number_cache = NumberCache(ttl_seconds=3600)
session_cache = SessionCache(ttl_seconds=1800)
license_cache = LicenseCache(ttl_seconds=600)
operation_cache = OperationCache(ttl_seconds=60)
