from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging
import time
import json
import os
import uuid
from collections import defaultdict
import jwt
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
from contextlib import contextmanager

app = FastAPI(
    title="Phoenix Cloud API",
    description="WhatsApp Phoenix Cloud API v1 — International Grade Infrastructure",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

security = HTTPBearer()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("phoenix_cloud.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("phoenix.cloud")

JWT_SECRET = os.getenv("PHOENIX_JWT_SECRET", "phoenix-cloud-super-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("PHOENIX_JWT_EXPIRE_MINUTES", "1440"))

PRO_TIER_LIMIT = 100
ELITE_TIER_LIMIT = None

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    password=os.getenv("REDIS_PASSWORD", ""),
    decode_responses=True
)

DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_SQLITE = not bool(DATABASE_URL)
DB_PATH = os.path.join(os.path.dirname(__file__), "phoenix.db")


def init_sqlite():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                license_key TEXT UNIQUE NOT NULL,
                tier TEXT NOT NULL CHECK(tier IN ('pro','elite','enterprise')),
                created_at TEXT NOT NULL,
                expires_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                phone TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                result TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                gateway TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS affiliates (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                ref_code TEXT UNIQUE NOT NULL,
                commission REAL NOT NULL DEFAULT 0.0,
                earnings REAL NOT NULL DEFAULT 0.0
            )
        """)
        conn.commit()


def get_db():
    if USE_SQLITE:
        return sqlite3.connect(DB_PATH)
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


@contextmanager
def db_cursor():
    conn = get_db()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class OperationRequest(BaseModel):
    phone: str = Field(..., min_length=7, max_length=15, description="Phone number with country code e.g. +923001234567")
    action: str = Field(..., description="permanent_ban | permanent_unban | temporary_ban | temporary_unban | status_check")
    duration_hours: Optional[int] = Field(None, ge=1, le=720, description="Duration for temporary_ban (1-720 hours)")
    license_key: Optional[str] = Field(None, description="Optional license key override")

    @validator("action")
    def validate_action(cls, v):
        allowed = {"permanent_ban", "permanent_unban", "temporary_ban", "temporary_unban", "status_check"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v

    @validator("phone")
    def validate_phone(cls, v):
        v = v.strip()
        if not v.startswith("+"):
            raise ValueError("Phone must start with + and include country code")
        return v


class StatsResponse(BaseModel):
    version: str
    uptime_seconds: float
    total_operations: int
    successful: int
    failed: int
    success_rate: float


class HistoryItem(BaseModel):
    operation_id: str
    user_id: str
    phone: str
    action: str
    status: str
    result: Optional[str]
    timestamp: str


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        tier = payload.get("tier")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return {"user_id": user_id, "tier": tier}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def check_rate_limit(user_id: str, tier: str):
    now = int(time.time())
    window = 60
    if tier == "elite":
        return True

    key = f"rate_limit:{user_id}:{now // window}"
    current = redis_client.incr(key)
    if current == 1:
        redis_client.expire(key, window + 1)

    if current > PRO_TIER_LIMIT:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded (100/min)")


def log_request(user_id: str, path: str, payload: dict, status_code: int, duration_ms: float):
    logger.info(json.dumps({
        "user_id": user_id,
        "path": path,
        "payload": payload,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "timestamp": datetime.utcnow().isoformat()
    }))


@app.get("/api/v1/stats", response_model=StatsResponse)
async def get_stats(user: dict = Depends(get_current_user)):
    start = time.perf_counter()
    try:
        check_rate_limit(user["user_id"], user["tier"])
        with db_cursor() as cur:
            if USE_SQLITE:
                cur.execute("SELECT COUNT(*) as total FROM operations WHERE user_id=?", (user["user_id"],))
                row = cur.fetchone()
                total = row[0] if row else 0
                cur.execute("SELECT COUNT(*) as successful FROM operations WHERE user_id=? AND status='success'", (user["user_id"],))
                row = cur.fetchone()
                successful = row[0] if row else 0
            else:
                cur.execute("SELECT COUNT(*) as total FROM operations WHERE user_id=%s", (user["user_id"],))
                row = cur.fetchone()
                total = row["total"] if row else 0
                cur.execute("SELECT COUNT(*) as successful FROM operations WHERE user_id=%s AND status='success'", (user["user_id"],))
                row = cur.fetchone()
                successful = row["successful"] if row else 0
        failed = total - successful
        success_rate = (successful / total * 100) if total else 0.0
        duration_ms = (time.perf_counter() - start) * 1000
        log_request(user["user_id"], "/api/v1/stats", {}, 200, duration_ms)
        return {
            "version": "Phoenix Ultra Pro v3.0",
            "uptime_seconds": time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0,
            "total_operations": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(success_rate, 2)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("stats error")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/history", response_model=List[HistoryItem])
async def get_history(user: dict = Depends(get_current_user), limit: int = 100, action: Optional[str] = None):
    start = time.perf_counter()
    try:
        check_rate_limit(user["user_id"], user["tier"])
        limit = max(1, min(limit, 500))
        with db_cursor() as cur:
            if action:
                if USE_SQLITE:
                    cur.execute(
                        "SELECT id, user_id, phone, action, status, result, timestamp FROM operations WHERE user_id=? AND action=? ORDER BY timestamp DESC LIMIT ?",
                        (user["user_id"], action, limit)
                    )
                else:
                    cur.execute(
                        "SELECT id, user_id, phone, action, status, result, timestamp FROM operations WHERE user_id=%s AND action=%s ORDER BY timestamp DESC LIMIT %s",
                        (user["user_id"], action, limit)
                    )
            else:
                if USE_SQLITE:
                    cur.execute(
                        "SELECT id, user_id, phone, action, status, result, timestamp FROM operations WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
                        (user["user_id"], limit)
                    )
                else:
                    cur.execute(
                        "SELECT id, user_id, phone, action, status, result, timestamp FROM operations WHERE user_id=%s ORDER BY timestamp DESC LIMIT %s",
                        (user["user_id"], limit)
                    )
            rows = cur.fetchall()
        result = []
        for row in rows:
            if USE_SQLITE:
                result.append({
                    "operation_id": row[0],
                    "user_id": row[1],
                    "phone": row[2],
                    "action": row[3],
                    "status": row[4],
                    "result": row[5],
                    "timestamp": row[6]
                })
            else:
                result.append({
                    "operation_id": row["id"],
                    "user_id": row["user_id"],
                    "phone": row["phone"],
                    "action": row["action"],
                    "status": row["status"],
                    "result": row["result"],
                    "timestamp": row["timestamp"]
                })
        duration_ms = (time.perf_counter() - start) * 1000
        log_request(user["user_id"], "/api/v1/history", {"limit": limit, "action": action}, 200, duration_ms)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("history error")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/v1/permanent-ban")
async def permanent_ban(req: OperationRequest, user: dict = Depends(get_current_user)):
    start = time.perf_counter()
    try:
        check_rate_limit(user["user_id"], user["tier"])
        result = await _enqueue_operation(user["user_id"], req.phone, "permanent_ban")
        duration_ms = (time.perf_counter() - start) * 1000
        log_request(user["user_id"], "/api/v1/permanent-ban", req.dict(), 202, duration_ms)
        return JSONResponse(content={"status": "accepted", "operation_id": result["operation_id"], "phone": req.phone, "action": "permanent_ban"}, status_code=202)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("permanent-ban error")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/v1/permanent-unban")
async def permanent_unban(req: OperationRequest, user: dict = Depends(get_current_user)):
    start = time.perf_counter()
    try:
        check_rate_limit(user["user_id"], user["tier"])
        result = await _enqueue_operation(user["user_id"], req.phone, "permanent_unban")
        duration_ms = (time.perf_counter() - start) * 1000
        log_request(user["user_id"], "/api/v1/permanent-unban", req.dict(), 202, duration_ms)
        return JSONResponse(content={"status": "accepted", "operation_id": result["operation_id"], "phone": req.phone, "action": "permanent_unban"}, status_code=202)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("permanent-unban error")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/v1/temporary-ban")
async def temporary_ban(req: OperationRequest, user: dict = Depends(get_current_user)):
    start = time.perf_counter()
    try:
        check_rate_limit(user["user_id"], user["tier"])
        if req.action != "temporary_ban":
            raise HTTPException(status_code=422, detail="action must be temporary_ban")
        if req.duration_hours is None:
            req.duration_hours = 24
        result = await _enqueue_operation(user["user_id"], req.phone, "temporary_ban", {"duration_hours": req.duration_hours})
        duration_ms = (time.perf_counter() - start) * 1000
        log_request(user["user_id"], "/api/v1/temporary-ban", req.dict(), 202, duration_ms)
        return JSONResponse(content={"status": "accepted", "operation_id": result["operation_id"], "phone": req.phone, "action": "temporary_ban", "duration_hours": req.duration_hours}, status_code=202)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("temporary-ban error")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/v1/temporary-unban")
async def temporary_unban(req: OperationRequest, user: dict = Depends(get_current_user)):
    start = time.perf_counter()
    try:
        check_rate_limit(user["user_id"], user["tier"])
        result = await _enqueue_operation(user["user_id"], req.phone, "temporary_unban")
        duration_ms = (time.perf_counter() - start) * 1000
        log_request(user["user_id"], "/api/v1/temporary-unban", req.dict(), 202, duration_ms)
        return JSONResponse(content={"status": "accepted", "operation_id": result["operation_id"], "phone": req.phone, "action": "temporary_unban"}, status_code=202)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("temporary-unban error")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/v1/status-check")
async def status_check(req: OperationRequest, user: dict = Depends(get_current_user)):
    start = time.perf_counter()
    try:
        check_rate_limit(user["user_id"], user["tier"])
        result = await _enqueue_operation(user["user_id"], req.phone, "status_check")
        duration_ms = (time.perf_counter() - start) * 1000
        log_request(user["user_id"], "/api/v1/status-check", req.dict(), 202, duration_ms)
        return JSONResponse(content={"status": "accepted", "operation_id": result["operation_id"], "phone": req.phone, "action": "status_check"}, status_code=202)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("status-check error")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.on_event("startup")
async def startup_event():
    app.state.start_time = time.time()
    init_sqlite()
    try:
        redis_client.ping()
        logger.info("Redis connected")
    except Exception:
        logger.warning("Redis not available — falling back to in-memory rate limiting")
    logger.info("Phoenix Cloud API started")


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


async def _enqueue_operation(user_id: str, phone: str, action: str, extra: Optional[dict] = None):
    operation_id = str(uuid.uuid4())
    payload = {"phone": phone, "action": action}
    if extra:
        payload.update(extra)
    now = datetime.utcnow().isoformat()
    with db_cursor() as cur:
        if USE_SQLITE:
            cur.execute(
                "INSERT INTO operations (id, user_id, phone, action, status, result, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (operation_id, user_id, phone, action, "queued", json.dumps(payload), now)
            )
        else:
            cur.execute(
                "INSERT INTO operations (id, user_id, phone, action, status, result, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (operation_id, user_id, phone, action, "queued", json.dumps(payload), now)
            )
    return {"operation_id": operation_id}
