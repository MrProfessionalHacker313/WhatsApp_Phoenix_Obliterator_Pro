import os
import json
import time
import logging
import threading
import queue
import uuid
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta

logger = logging.getLogger("phoenix.cloud_client")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from ..config import config as _local_config
from ..core.engine import phoenix as _local_engine


CLOUD_API_URL = os.getenv("PHOENIX_CLOUD_API_URL", "https://phoenix.example.com")
CLOUD_API_TOKEN = os.getenv("PHOENIX_CLOUD_API_TOKEN", "")
LICENSE_KEY = os.getenv("PHOENIX_LICENSE_KEY", "")
OFFLINE_QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "offline_queue.json")
OFFLINE_QUEUE_PATH = os.path.abspath(OFFLINE_QUEUE_PATH)
SYNC_INTERVAL_SECONDS = int(os.getenv("PHOENIX_SYNC_INTERVAL", "60"))
MAX_OFFLINE_QUEUE = int(os.getenv("PHOENIX_MAX_OFFLINE_QUEUE", "500"))


class CloudClient:
    def __init__(self, api_url: str = CLOUD_API_URL, token: str = CLOUD_API_TOKEN, license_key: str = LICENSE_KEY):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.license_key = license_key
        self._online = self._check_online()
        self._offline_queue: List[Dict[str, Any]] = self._load_offline_queue()
        self._sync_thread: Optional[threading.Thread] = None
        self._stop_sync = threading.Event()
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        if self._online:
            self._start_sync()

    def _check_online(self) -> bool:
        if not REQUESTS_AVAILABLE:
            return False
        try:
            resp = requests.get(f"{self.api_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    @property
    def is_online(self) -> bool:
        return self._online

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _post(self, path: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not REQUESTS_AVAILABLE:
            return None
        try:
            resp = requests.post(f"{self.api_url}{path}", json=payload, headers=self._headers(), timeout=30)
            if resp.status_code in (200, 202):
                return resp.json()
            if resp.status_code == 401:
                logger.error("Unauthorized — check API token")
            return None
        except Exception as e:
            logger.debug("Cloud request failed: %s", e)
            return None

    def _enqueue_offline(self, payload: Dict[str, Any]):
        if len(self._offline_queue) >= MAX_OFFLINE_QUEUE:
            self._offline_queue.pop(0)
        self._offline_queue.append({
            "queued_at": datetime.utcnow().isoformat(),
            "payload": payload
        })
        self._persist_offline_queue()
        logger.info("Operation queued offline: %s", payload.get("action"))

    def _load_offline_queue(self) -> List[Dict[str, Any]]:
        try:
            if os.path.exists(OFFLINE_QUEUE_PATH):
                with open(OFFLINE_QUEUE_PATH, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _persist_offline_queue(self):
        try:
            with open(OFFLINE_QUEUE_PATH, "w") as f:
                json.dump(self._offline_queue, f)
        except Exception as e:
            logger.warning("Failed to persist offline queue: %s", e)

    def _flush_offline(self) -> int:
        if not self._online or not self._offline_queue:
            return 0
        failed = 0
        pending = self._offline_queue.copy()
        self._offline_queue = []
        for item in pending:
            payload = item.get("payload", {})
            path = payload.pop("_path", "")
            if not path:
                continue
            if not self._post(path, payload):
                failed += 1
                self._offline_queue.append(item)
        self._persist_offline_queue()
        logger.info("Flushed %d offline operations (%d failed)", len(pending) - failed, failed)
        return len(pending) - failed

    def _start_sync(self):
        if self._sync_thread and self._sync_thread.is_alive():
            return
        self._stop_sync.clear()
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()

    def _sync_loop(self):
        while not self._stop_sync.is_set():
            time.sleep(SYNC_INTERVAL_SECONDS)
            if self._online:
                try:
                    self._online = self._check_online()
                except Exception:
                    self._online = False
                if self._online:
                    self._flush_offline()

    def add_listener(self, fn: Callable[[Dict[str, Any]], None]):
        self._listeners.append(fn)

    def _notify(self, event: Dict[str, Any]):
        for fn in self._listeners:
            try:
                fn(event)
            except Exception:
                pass

    def set_token(self, token: str):
        self.token = token

    def set_license(self, license_key: str):
        self.license_key = license_key

    def permanent_ban(self, phone: str) -> Dict[str, Any]:
        payload = {"phone": phone, "action": "permanent_ban", "license_key": self.license_key}
        return self._dispatch("/api/v1/permanent-ban", payload, "permanent_ban", phone)

    def permanent_unban(self, phone: str) -> Dict[str, Any]:
        payload = {"phone": phone, "action": "permanent_unban", "license_key": self.license_key}
        return self._dispatch("/api/v1/permanent-unban", payload, "permanent_unban", phone)

    def temporary_ban(self, phone: str, duration_hours: int = 24) -> Dict[str, Any]:
        payload = {"phone": phone, "action": "temporary_ban", "duration_hours": duration_hours, "license_key": self.license_key}
        return self._dispatch("/api/v1/temporary-ban", payload, "temporary_ban", phone)

    def temporary_unban(self, phone: str) -> Dict[str, Any]:
        payload = {"phone": phone, "action": "temporary_unban", "license_key": self.license_key}
        return self._dispatch("/api/v1/temporary-unban", payload, "temporary_unban", phone)

    def status_check(self, phone: str) -> Dict[str, Any]:
        payload = {"phone": phone, "action": "status_check", "license_key": self.license_key}
        return self._dispatch("/api/v1/status-check", payload, "status_check", phone)

    def get_stats(self) -> Dict[str, Any]:
        if self._online:
            data = self._post("/api/v1/stats", {})
            if data:
                return data
        return self._local_stats()

    def get_history(self, limit: int = 100, action: Optional[str] = None) -> List[Dict[str, Any]]:
        if self._online:
            params = {"limit": limit}
            if action:
                params["action"] = action
            try:
                resp = requests.get(f"{self.api_url}/api/v1/history", headers=self._headers(), params=params, timeout=30)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        return []

    def _dispatch(self, path: str, payload: Dict[str, Any], action: str, phone: str) -> Dict[str, Any]:
        event = {"action": action, "phone": phone, "mode": "cloud" if self._online else "offline", "timestamp": datetime.utcnow().isoformat()}
        if self._online:
            result = self._post(path, payload)
            if result:
                event["status"] = "accepted"
                event["operation_id"] = result.get("operation_id")
                self._notify(event)
                return {"mode": "cloud", "status": "accepted", "operation_id": result.get("operation_id"), "phone": phone, "action": action}
            self._online = False
        event["mode"] = "offline"
        self._enqueue_offline({"_path": path, **payload})
        local_result = self._run_local(action, phone)
        event["status"] = "offline_local"
        event["local_result"] = local_result
        self._notify(event)
        return {"mode": "offline", "status": "offline_local", "local_result": local_result, "phone": phone, "action": action}

    def _run_local(self, action: str, phone: str) -> Dict[str, Any]:
        logger.info("Running local fallback for %s on %s", action, phone)
        try:
            report = _local_engine.process_number(phone, action)
            return {"success": report.get("success", False), "details": report.get("details"), "error": report.get("error")}
        except Exception as e:
            logger.exception("Local fallback failed")
            return {"success": False, "error": str(e)}

    def _local_stats(self) -> Dict[str, Any]:
        try:
            return _local_engine.get_stats()
        except Exception:
            return {"version": "Phoenix Ultra Pro v3.0", "total_operations": 0, "successful": 0, "failed": 0, "success_rate": 0.0}

    def sync_status(self) -> Dict[str, Any]:
        synced = 0
        if self._online:
            synced = self._flush_offline()
        return {
            "online": self._online,
            "api_url": self.api_url,
            "queued_operations": len(self._offline_queue),
            "synced_operations": synced,
            "timestamp": datetime.utcnow().isoformat()
        }

    def shutdown(self):
        self._stop_sync.set()
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
        self._persist_offline_queue()


cloud_client = CloudClient()
