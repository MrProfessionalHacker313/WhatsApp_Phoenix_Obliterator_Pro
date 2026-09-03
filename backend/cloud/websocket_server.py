#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PHOENIX WEBSOCKET SERVER — Real-time Dashboard Broadcasting
"""

import asyncio
import json
import logging
import os
import time
import jwt
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("phoenix.websocket")

app = FastAPI(title="Phoenix WebSocket Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

JWT_SECRET = os.getenv("PHOENIX_JWT_SECRET", "phoenix-cloud-super-secret-change-me")
JWT_ALGORITHM = "HS256"

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.user_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.user_tiers: Dict[str, str] = {}
        self.rate_limits: Dict[str, List[float]] = defaultdict(list)
        self.message_count: Dict[str, int] = defaultdict(int)
        self.last_broadcast = time.time()

    async def connect(self, websocket: WebSocket, user_id: str, tier: str = "pro"):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.user_connections[user_id].add(websocket)
        self.user_tiers[user_id] = tier
        logger.info(f"Dashboard connected: {user_id} (tier={tier}), total={len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        self.active_connections.discard(websocket)
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
                self.user_tiers.pop(user_id, None)
        logger.info(f"Dashboard disconnected: {user_id}, total={len(self.active_connections)}")

    def check_rate_limit(self, user_id: str, tier: str, max_events_per_minute: int = 120) -> bool:
        if tier == "elite":
            return True
        now = time.time()
        window = 60
        self.rate_limits[user_id] = [t for t in self.rate_limits[user_id] if now - t < window]
        if len(self.rate_limits[user_id]) >= max_events_per_minute:
            return False
        self.rate_limits[user_id].append(now)
        return True

    async def broadcast(self, message: dict, exclude: Optional[WebSocket] = None, target_tier: Optional[str] = None):
        payload = json.dumps(message, default=str)
        dead: List[WebSocket] = []
        for conn in list(self.active_connections):
            if conn == exclude:
                continue
            try:
                if target_tier:
                    user_id = next((uid for uid, conns in self.user_connections.items() if conn in conns), None)
                    if user_id and self.user_tiers.get(user_id) != target_tier:
                        continue
                await conn.send_text(payload)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.active_connections.discard(d)
            for uid in list(self.user_connections.keys()):
                self.user_connections[uid].discard(d)

    async def send_to_user(self, user_id: str, message: dict):
        payload = json.dumps(message, default=str)
        dead: List[WebSocket] = []
        for conn in list(self.user_connections.get(user_id, [])):
            try:
                await conn.send_text(payload)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.user_connections[user_id].discard(d)

manager = ConnectionManager()

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        tier = payload.get("tier", "pro")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user_id, tier)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "ts": time.time()}))
                elif msg.get("type") == "subscribe":
                    await websocket.send_text(json.dumps({"type": "subscribed", "channel": msg.get("channel", "all")}))
                elif msg.get("type") == "export_request":
                    await websocket.send_text(json.dumps({
                        "type": "export_data",
                        "format": msg.get("format", "json"),
                        "data": []
                    }))
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception:
        manager.disconnect(websocket, user_id)

@app.get("/api/v1/ws/stats")
async def ws_stats():
    return {
        "active_dashboards": len(manager.active_connections),
        "users_online": len(manager.user_connections),
        "total_broadcasts": manager.message_count.get("global", 0),
        "uptime_seconds": time.time() - manager.last_broadcast
    }

@app.post("/api/v1/ws/broadcast")
async def ws_broadcast(payload: dict, user: dict = Depends(security)):
    token = user["credentials"].credentials
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        uid = decoded.get("sub")
        tier = decoded.get("tier", "pro")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not manager.check_rate_limit(uid, tier, max_events_per_minute=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    manager.message_count["global"] += 1
    await manager.broadcast(payload)
    return {"status": "broadcasted", "connections": len(manager.active_connections)}
