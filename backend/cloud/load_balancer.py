import os
import json
import time
import random
import logging
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

logger = logging.getLogger("phoenix.loadbalancer")

PROXY_POOL_ENV = os.getenv("PHOENIX_PROXY_POOL", "[]")
BACKUP_SERVERS_ENV = os.getenv("PHOENIX_BACKUP_SERVERS", "[]")

try:
    proxy_pool: List[Dict[str, Any]] = json.loads(PROXY_POOL_ENV)
except Exception:
    proxy_pool = []

try:
    backup_servers: List[str] = json.loads(BACKUP_SERVERS_ENV)
except Exception:
    backup_servers = []

MAX_SESSIONS_PER_PROXY = int(os.getenv("PHOENIX_MAX_SESSIONS_PER_PROXY", "3"))
AUTO_SCALE_THRESHOLD = int(os.getenv("PHOENIX_AUTO_SCALE_THRESHOLD", "20"))
FAILOVER_GRACE_SECONDS = int(os.getenv("PHOENIX_FAILOVER_GRACE_SECONDS", "5"))


@dataclass
class ProxyEntry:
    ip: str
    port: int
    country: str
    latency_ms: float = 9999.0
    active_sessions: int = 0
    failed_count: int = 0
    last_used: Optional[str] = None
    healthy: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ServerNode:
    url: str
    healthy: bool = True
    load: float = 0.0
    active_operations: int = 0
    last_health_check: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LoadBalancer:
    def __init__(self):
        self._lock = threading.Lock()
        self._proxy_entries: List[ProxyEntry] = []
        self._server_nodes: List[ServerNode] = []
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self._failed_operations: Dict[str, int] = {}
        self._initialize_pools()

    def _initialize_pools(self):
        for p in proxy_pool:
            if isinstance(p, dict):
                self._proxy_entries.append(ProxyEntry(
                    ip=p.get("ip", "127.0.0.1"),
                    port=int(p.get("port", 8080)),
                    country=p.get("country", "US")
                ))
        for s in backup_servers:
            self._server_nodes.append(ServerNode(url=s))
        if not self._server_nodes:
            self._server_nodes.append(ServerNode(url="local://default"))
        logger.info("LoadBalancer initialized with %d proxies and %d servers", len(self._proxy_entries), len(self._server_nodes))

    def get_best_proxy(self, phone_number: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            healthy = [p for p in self._proxy_entries if p.healthy and p.active_sessions < MAX_SESSIONS_PER_PROXY]
            if not healthy:
                healthy = [p for p in self._proxy_entries if p.healthy]
            if not healthy:
                logger.warning("No healthy proxies available")
                return None
            healthy.sort(key=lambda p: (p.latency_ms, p.active_sessions, -p.failed_count))
            best = healthy[0]
            best.active_sessions += 1
            best.last_used = datetime.utcnow().isoformat()
            return best.to_dict()

    def release_proxy(self, proxy: Dict[str, Any]):
        with self._lock:
            for p in self._proxy_entries:
                if p.ip == proxy.get("ip") and p.port == proxy.get("port"):
                    p.active_sessions = max(0, p.active_sessions - 1)
                    break

    def mark_proxy_failed(self, proxy: Dict[str, Any]):
        with self._lock:
            for p in self._proxy_entries:
                if p.ip == proxy.get("ip") and p.port == proxy.get("port"):
                    p.failed_count += 1
                    p.active_sessions = max(0, p.active_sessions - 1)
                    if p.failed_count >= 5:
                        p.healthy = False
                        logger.warning("Proxy marked unhealthy: %s:%s", p.ip, p.port)
                    break

    def update_proxy_latency(self, proxy: Dict[str, Any], latency_ms: float):
        with self._lock:
            for p in self._proxy_entries:
                if p.ip == proxy.get("ip") and p.port == proxy.get("port"):
                    p.latency_ms = round(latency_ms, 2)
                    break

    def get_server_for_operation(self) -> Optional[str]:
        with self._lock:
            healthy = [s for s in self._server_nodes if s.healthy]
            if not healthy:
                return None
            healthy.sort(key=lambda s: (s.load, s.active_operations))
            selected = healthy[0]
            selected.active_operations += 1
            selected.load = min(1.0, selected.load + 0.05)
            return selected.url

    def release_server(self, server_url: str):
        with self._lock:
            for s in self._server_nodes:
                if s.url == server_url:
                    s.active_operations = max(0, s.active_operations - 1)
                    s.load = max(0.0, s.load - 0.05)
                    break

    def mark_server_unhealthy(self, server_url: str):
        with self._lock:
            for s in self._server_nodes:
                if s.url == server_url:
                    s.healthy = False
                    logger.warning("Server marked unhealthy: %s", server_url)
                    break

    def failover(self, current_server_url: str) -> Optional[str]:
        logger.info("Initiating failover from %s", current_server_url)
        with self._lock:
            for s in self._server_nodes:
                if s.url == current_server_url:
                    s.healthy = False
            healthy = [s for s in self._server_nodes if s.healthy]
        if not healthy:
            logger.error("No healthy backup servers available")
            return None
        fallback = min(healthy, key=lambda s: (s.load, s.active_operations))
        logger.info("Failover to %s", fallback.url)
        return fallback.url

    def record_operation_result(self, server_url: str, success: bool):
        with self._lock:
            for s in self._server_nodes:
                if s.url == server_url:
                    if success:
                        s.load = max(0.0, s.load - 0.02)
                    else:
                        s.load = min(1.0, s.load + 0.05)
                        self._failed_operations[server_url] = self._failed_operations.get(server_url, 0) + 1
                        if self._failed_operations.get(server_url, 0) >= 10:
                            s.healthy = False
                    break

    def get_pool_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "proxies": [p.to_dict() for p in self._proxy_entries],
                "servers": [s.to_dict() for s in self._server_nodes],
                "active_sessions": len(self._active_sessions),
                "timestamp": datetime.utcnow().isoformat()
            }

    def register_session(self, session_id: str, proxy: Dict[str, Any], server_url: str):
        with self._lock:
            self._active_sessions[session_id] = {
                "proxy": proxy,
                "server_url": server_url,
                "created_at": datetime.utcnow().isoformat()
            }

    def unregister_session(self, session_id: str):
        with self._lock:
            info = self._active_sessions.pop(session_id, None)
            if info:
                self.release_proxy(info.get("proxy", {}))
                self.release_server(info.get("server_url", ""))

    def auto_scale_sessions(self) -> Dict[str, Any]:
        total_capacity = sum(max(0, MAX_SESSIONS_PER_PROXY - p.active_sessions) for p in self._proxy_entries)
        with self._lock:
            active = len(self._active_sessions)
        scale_up = active >= AUTO_SCALE_THRESHOLD and total_capacity > 0
        return {
            "active_sessions": active,
            "available_capacity": total_capacity,
            "scale_up_recommended": scale_up,
            "timestamp": datetime.utcnow().isoformat()
        }

    def health_check(self) -> Dict[str, Any]:
        with self._lock:
            healthy_proxies = sum(1 for p in self._proxy_entries if p.healthy)
            healthy_servers = sum(1 for s in self._server_nodes if s.healthy)
        return {
            "healthy_proxies": healthy_proxies,
            "total_proxies": len(self._proxy_entries),
            "healthy_servers": healthy_servers,
            "total_servers": len(self._server_nodes),
            "timestamp": datetime.utcnow().isoformat()
        }


load_balancer = LoadBalancer()
