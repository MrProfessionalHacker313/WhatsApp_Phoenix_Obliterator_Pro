"""
PHOENIX EAGLE — SHARING STORAGE HELPERS
=======================================
Tiny atomic JSON store shared by all sharing modules. Every record set is a
single JSON file written via a temp file + ``os.replace`` so a crash mid-write
can never corrupt prior state.

The files produced here are plain data — no secrets are stored unencrypted
beyond the public-facing share registry (which only holds user-visible info).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("phoenix.sharing.storage")

# Directory that holds all sharing state, next to this module.
DATA_DIR = os.path.dirname(os.path.abspath(__file__))


class ShareStore:
    """Atomic JSON-backed key/value store for one logical collection."""

    def __init__(self, name: str, data_dir: str | None = None):
        self.path = os.path.join(data_dir or DATA_DIR, f"{name}.json")
        self._data: dict[str, Any] | None = None

    # ------------------------------------------------------------- load/save
    def load(self) -> dict[str, Any]:
        """Return the on-disk collection, creating an empty one if absent."""
        if self._data is not None:
            return self._data
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                self._data = raw if isinstance(raw, dict) else {}
            except Exception as exc:
                logger.warning("Could not load %s: %s", self.path, exc)
                self._data = {}
        else:
            self._data = {}
        return self._data

    def save(self) -> None:
        """Persist the in-memory collection atomically."""
        if self._data is None:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
            os.replace(tmp, self.path)
        except Exception as exc:
            logger.error("Could not persist %s: %s", self.path, exc)
            raise

    # ------------------------------------------------------------- accessors
    def get(self, key: str, default: Any = None) -> Any:
        return self.load().get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.load()[key] = value
        self.save()

    def contains(self, key: str) -> bool:
        return key in self.load()

    def keys(self) -> list[str]:
        return list(self.load().keys())

    def all(self) -> dict[str, Any]:
        return dict(self.load())

    def delete(self, key: str) -> bool:
        data = self.load()
        if key in data:
            del data[key]
            self.save()
            return True
        return False

    def mutate(self, key: str, updater):
        """Apply ``updater(record) -> record`` to the record at ``key``."""
        data = self.load()
        record = data.get(key, {})
        data[key] = updater(record)
        self.save()
        return data[key]


# Shared store instances used across the package. Keeping them as module-level
# singletons matches the ``CONFIG``-style convention used by the payment module.
SHARE_LINKS = ShareStore("share_links")          # ref_code -> link record
AFFILIATES = ShareStore("affiliates")            # affiliate_id -> affiliate
COMMISSIONS = ShareStore("commissions")          # stable -> commission record
WITHDRAWALS = ShareStore("withdrawals")          # withdrawal_id -> withdrawal
ASSETS = ShareStore("assets")                    # asset_id -> download record
SALES_LOG = ShareStore("sales_log")              # payment_id -> sale record