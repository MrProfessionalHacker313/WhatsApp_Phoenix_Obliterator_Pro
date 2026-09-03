import os
import json
import time
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

logger = logging.getLogger("phoenix.database")

BACKUP_INTERVAL_SECONDS = 6 * 60 * 60
BACKUP_DIR = Path(os.getenv("PHOENIX_BACKUP_DIR", "backups"))
BACKUP_DIR.mkdir(exist_ok=True)


class DatabaseManager:
    def __init__(self, database_url: Optional[str] = None, sqlite_path: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL", "")
        self.sqlite_path = Path(sqlite_path or os.getenv("SQLITE_PATH", "phoenix.db"))
        self.use_postgres = bool(self.database_url) and POSTGRES_AVAILABLE
        self._ensure_schema()

    def _get_connection(self):
        if self.use_postgres:
            return psycopg2.connect(self.database_url)
        return sqlite3.connect(self.sqlite_path)

    @contextmanager
    def connection(self):
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self):
        with self.connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        license_key TEXT UNIQUE NOT NULL,
                        tier TEXT NOT NULL CHECK(tier IN ('pro','elite','enterprise')),
                        created_at TEXT NOT NULL,
                        expires_at TEXT
                    )
                """)
                cur.execute("""
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
                cur.execute("""
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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS affiliates (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        ref_code TEXT UNIQUE NOT NULL,
                        commission REAL NOT NULL DEFAULT 0.0,
                        earnings REAL NOT NULL DEFAULT 0.0
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_operations_user_id ON operations(user_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_operations_timestamp ON operations(timestamp)")
            else:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        license_key TEXT UNIQUE NOT NULL,
                        tier TEXT NOT NULL CHECK(tier IN ('pro','elite','enterprise')),
                        created_at TEXT NOT NULL,
                        expires_at TEXT
                    )
                """)
                cur.execute("""
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
                cur.execute("""
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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS affiliates (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        ref_code TEXT UNIQUE NOT NULL,
                        commission REAL NOT NULL DEFAULT 0.0,
                        earnings REAL NOT NULL DEFAULT 0.0
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_operations_user_id ON operations(user_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_operations_timestamp ON operations(timestamp)")
            conn.commit()

    def insert_user(self, user_id: str, email: str, license_key: str, tier: str, expires_at: Optional[str] = None):
        with self.connection() as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            if self.use_postgres:
                cur.execute(
                    "INSERT INTO users (id, email, license_key, tier, created_at, expires_at) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (user_id, email, license_key, tier, now, expires_at)
                )
            else:
                cur.execute(
                    "INSERT OR IGNORE INTO users (id, email, license_key, tier, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, email, license_key, tier, now, expires_at)
                )

    def get_user_by_license(self, license_key: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("SELECT id, email, license_key, tier, created_at, expires_at FROM users WHERE license_key=%s", (license_key,))
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0], "email": row[1], "license_key": row[2],
                    "tier": row[3], "created_at": row[4], "expires_at": row[5]
                }
            else:
                cur.execute("SELECT id, email, license_key, tier, created_at, expires_at FROM users WHERE license_key=?", (license_key,))
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0], "email": row[1], "license_key": row[2],
                    "tier": row[3], "created_at": row[4], "expires_at": row[5]
                }

    def insert_operation(self, operation_id: str, user_id: str, phone: str, action: str, status: str = "queued", result: Optional[Dict[str, Any]] = None):
        with self.connection() as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            result_json = json.dumps(result) if result is not None else None
            if self.use_postgres:
                cur.execute(
                    "INSERT INTO operations (id, user_id, phone, action, status, result, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (operation_id, user_id, phone, action, status, result_json, now)
                )
            else:
                cur.execute(
                    "INSERT INTO operations (id, user_id, phone, action, status, result, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (operation_id, user_id, phone, action, status, result_json, now)
                )

    def update_operation_status(self, operation_id: str, status: str, result: Optional[Dict[str, Any]] = None):
        with self.connection() as conn:
            cur = conn.cursor()
            result_json = json.dumps(result) if result is not None else None
            if self.use_postgres:
                cur.execute("UPDATE operations SET status=%s, result=%s WHERE id=%s", (status, result_json, operation_id))
            else:
                cur.execute("UPDATE operations SET status=?, result=? WHERE id=?", (status, result_json, operation_id))

    def get_operations(self, user_id: str, limit: int = 100, action: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.cursor()
            if action:
                if self.use_postgres:
                    cur.execute(
                        "SELECT id, user_id, phone, action, status, result, timestamp FROM operations WHERE user_id=%s AND action=%s ORDER BY timestamp DESC LIMIT %s",
                        (user_id, action, limit)
                    )
                else:
                    cur.execute(
                        "SELECT id, user_id, phone, action, status, result, timestamp FROM operations WHERE user_id=? AND action=? ORDER BY timestamp DESC LIMIT ?",
                        (user_id, action, limit)
                    )
            else:
                if self.use_postgres:
                    cur.execute(
                        "SELECT id, user_id, phone, action, status, result, timestamp FROM operations WHERE user_id=%s ORDER BY timestamp DESC LIMIT %s",
                        (user_id, limit)
                    )
                else:
                    cur.execute(
                        "SELECT id, user_id, phone, action, status, result, timestamp FROM operations WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
                        (user_id, limit)
                    )
            rows = cur.fetchall()
            results = []
            for row in rows:
                if self.use_postgres:
                    results.append({
                        "id": row[0], "user_id": row[1], "phone": row[2],
                        "action": row[3], "status": row[4], "result": row[5], "timestamp": row[6]
                    })
                else:
                    results.append({
                        "id": row[0], "user_id": row[1], "phone": row[2],
                        "action": row[3], "status": row[4], "result": row[5], "timestamp": row[6]
                    })
            return results

    def get_stats(self, user_id: str) -> Dict[str, Any]:
        with self.connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("SELECT COUNT(*) as total FROM operations WHERE user_id=%s", (user_id,))
                row = cur.fetchone()
                total = row["total"] if row else 0
                cur.execute("SELECT COUNT(*) as successful FROM operations WHERE user_id=%s AND status='success'", (user_id,))
                row = cur.fetchone()
                successful = row["successful"] if row else 0
            else:
                cur.execute("SELECT COUNT(*) FROM operations WHERE user_id=?", (user_id,))
                row = cur.fetchone()
                total = row[0] if row else 0
                cur.execute("SELECT COUNT(*) FROM operations WHERE user_id=? AND status='success'", (user_id,))
                row = cur.fetchone()
                successful = row[0] if row else 0
            failed = total - successful
            success_rate = (successful / total * 100) if total else 0.0
            return {
                "total_operations": total,
                "successful": successful,
                "failed": failed,
                "success_rate": round(success_rate, 2)
            }

    def insert_payment(self, payment_id: str, user_id: str, amount: float, currency: str, gateway: str, status: str):
        with self.connection() as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            if self.use_postgres:
                cur.execute(
                    "INSERT INTO payments (id, user_id, amount, currency, gateway, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (payment_id, user_id, amount, currency, gateway, status, now)
                )
            else:
                cur.execute(
                    "INSERT INTO payments (id, user_id, amount, currency, gateway, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (payment_id, user_id, amount, currency, gateway, status, now)
                )

    def insert_affiliate(self, affiliate_id: str, user_id: str, ref_code: str):
        with self.connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute(
                    "INSERT INTO affiliates (id, user_id, ref_code, commission, earnings) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (affiliate_id, user_id, ref_code, 0.0, 0.0)
                )
            else:
                cur.execute(
                    "INSERT OR IGNORE INTO affiliates (id, user_id, ref_code, commission, earnings) VALUES (?, ?, ?, ?, ?)",
                    (affiliate_id, user_id, ref_code, 0.0, 0.0)
                )

    def backup(self) -> Optional[str]:
        try:
            if self.use_postgres:
                return self._backup_postgres()
            return self._backup_sqlite()
        except Exception as e:
            logger.exception("Backup failed")
            return None

    def _backup_sqlite(self) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"phoenix_backup_{timestamp}.sqlite"
        with sqlite3.connect(self.sqlite_path) as src:
            with sqlite3.connect(backup_file) as dst:
                src.backup(dst)
        logger.info("SQLite backup created: %s", backup_file)
        self._purge_old_backups()
        return str(backup_file)

    def _backup_postgres(self) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"phoenix_backup_{timestamp}.sql"
        with open(backup_file, "w") as f:
            with self.connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
                tables = [r[0] if isinstance(r, tuple) else r["table_name"] for r in cur.fetchall()]
                for table in tables:
                    f.write(f"\n-- Table: {table}\n")
                    if POSTGRES_AVAILABLE:
                        cur.copy_expert(f"COPY {table} TO STDOUT WITH CSV HEADER", f)
                f.write("\n")
        logger.info("PostgreSQL backup created: %s", backup_file)
        self._purge_old_backups()
        return str(backup_file)

    def _purge_old_backups(self, keep: int = 20):
        backups = sorted(BACKUP_DIR.glob("phoenix_backup_*"))
        for old in backups[:-keep]:
            try:
                old.unlink()
                logger.info("Purged old backup: %s", old)
            except Exception:
                pass

    def start_auto_backup(self):
        def _loop():
            while True:
                time.sleep(BACKUP_INTERVAL_SECONDS)
                self.backup()
        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        logger.info("Auto-backup scheduled every %d seconds", BACKUP_INTERVAL_SECONDS)


db = DatabaseManager()


def start_background_tasks():
    db.start_auto_backup()
