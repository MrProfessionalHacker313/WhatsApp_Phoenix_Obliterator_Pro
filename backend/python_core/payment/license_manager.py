"""
PHOENIX EAGLE — LICENSE MANAGER
===============================
Hardware-locked, RSA-2048-signed license keys.

Design
------
* The issuing side holds an RSA private key. The client embeds the
  corresponding public key (license_public.pem) so it can cryptographically
  verify a license OFFLINE — no network required for activation.
* A license is a signed JSON payload containing: tier, expiry timestamp,
  machine-id digest, a license UUID and issuer metadata. The signature is a
  PKCS#1 v1.5 RSA signature over the canonical payload (SHA-256).
* Hardware locking: the machine ID is a stable digest of platform + hostname
  + primary MAC + user. The payload stores a salted digest of that ID so a
  license can't be silently moved to another machine.
* Validation is two-phase:
    - offline : verify RSA signature + integrity + expiry + machine binding
    - online  : (optional) re-confirm against the payment/issuer server

Keys
----
* On first use, if no keypair exists the manager generates one and writes
  private + public into payment/keyset/. The public key is also mirrored to
  license_public.pem inside the package for embedded offline verification.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import logging
import os
import platform
import re
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)

from .config import (
    CONFIG,
    LICENSE_FILE,
    LICENSE_PUBKEY_FILE,
    RSA_PRIVATE_KEY_FILE,
    PLANS,
    LicenseStatus,
    LicenseTier,
)

logger = logging.getLogger("phoenix.payment.license")

# License payload version. Bump when the schema changes.
PAYLOAD_VERSION = 1

# Defensive upper bound on valid license length. "Elite = lifetime" is capped
# here rather than being truly infinite so expiry math stays safe.
MAX_LICENSE_DAYS = 3650


# ============================================================================
# Machine ID generation (hardware locking)
# ============================================================================
def _normalise_mac(raw: str) -> str:
    """Strip separators and upper-case a MAC address string."""
    return re.sub(r"[^0-9A-Fa-f]", "", raw).upper()


def _stable_mac() -> str:
    """Return the first stable MAC address we can find, else a placeholder."""
    try:
        import uuid as _uuid
        mac = getattr(_uuid, "getnode", lambda: 0)()
        if mac and mac != -1:
            return f"{mac:012X}"
    except Exception:
        pass

    candidates = []
    if sys.platform.startswith("win"):
        try:
            out = subprocess.check_output(
                ["getmac", "/FO", "CSV", "/NH"], text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in out.splitlines():
                name = line.strip().split(",")[-1].strip('"')
                if re.match(r"^[0-9A-Fa-f-]{17}$", name):
                    candidates.append(_normalise_mac(name))
        except Exception:
            pass
    else:
        for iface in ("eth0", "ens33", "en0", "wlan0", "wlp2s0"):
            try:
                with open(f"/sys/class/net/{iface}/address") as fh:
                    candidates.append(_normalise_mac(fh.read().strip()))
            except Exception:
                pass
    return candidates[0] if candidates else "NO-MAC-FOUND"


def generate_machine_id(seed_salt: str = "phoenix-eagle-2026") -> str:
    """
    Build a stable, hardware-bound machine identifier.

    Combines platform, machine, node, MAC, processor count and the current
    user into a digest. Returns a hex digest (64 chars).
    """
    user = ""
    try:
        user = getpass.getuser()
    except Exception:
        pass

    node = ""
    try:
        node = socket.gethostname()
    except Exception:
        pass

    node_hex = ""
    try:
        node_int = uuid.getnode()
        node_hex = f"{node_int:012X}"
    except Exception:
        pass

    try:
        proc_count = str(os.cpu_count() or 1)
    except Exception:
        proc_count = "1"

    raw = "|".join([
        platform.system() or "",
        platform.release() or "",
        platform.machine() or "",
        node or "",
        node_hex or "",
        _stable_mac(),
        user or "",
        proc_count,
        seed_salt,
    ])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    # Double-hash with a pepper baked into the binary for extra stability.
    return hashlib.sha256((digest + "::pepper-v1").encode("utf-8")).hexdigest()
# ============================================================================
# LicenseManager
# ============================================================================
class LicenseManager:
    """
    Generates, signs, stores and validates RSA-2048 hardware-locked licenses.

    Constructed either server-side (has private key -> can sign new licenses)
    or client-side (embedded public key -> can verify offline).
    """

    def __init__(self, private_key_path: str | None = None,
                 public_key_path: str | None = None):
        self.private_key_path = private_key_path or RSA_PRIVATE_KEY_FILE
        # Primary public key lives beside the private key in the keyset; the
        # standalone license_public.pem is a copied mirror for embedding.
        self.public_key_path = public_key_path or \
            os.path.join(os.path.dirname(RSA_PRIVATE_KEY_FILE),
                         "license_public.pem")
        self.mirror_public_key_path = LICENSE_PUBKEY_FILE
        self._private_key = None
        self._public_key = None
        self.machine_id = generate_machine_id()

    # --------------------------------------------------------- key handling
    def _load_or_create_keys(self) -> None:
        """Ensure a valid keypair exists; generate one on first run."""
        if not (os.path.exists(self.private_key_path) and
                os.path.exists(self.public_key_path)):
            self._bootstrap_keypair()
        try:
            with open(self.private_key_path, "rb") as fh:
                self._private_key = load_pem_private_key(fh.read(), password=None)
            with open(self.public_key_path, "rb") as fh:
                self._public_key = load_pem_public_key(fh.read())
        except Exception as exc:  # corrupted keys -> regenerate
            logger.warning("Corrupted keypair detected, regenerating: %s", exc)
            self._bootstrap_keypair()

    def _bootstrap_keypair(self) -> None:
        keyset_dir = os.path.dirname(self.private_key_path) or "."
        os.makedirs(keyset_dir, exist_ok=True)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()

        with open(self.private_key_path, "wb") as fh:
            fh.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        with open(self.public_key_path, "wb") as fh:
            fh.write(public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ))

        # Mirror the public key to the standalone copy used for embedding /
        # offline verification (must be a DIFFERENT file than the source).
        try:
            if os.path.abspath(self.public_key_path) != \
                    os.path.abspath(self.mirror_public_key_path):
                with open(self.public_key_path, "rb") as src:
                    pub_data = src.read()
                with open(self.mirror_public_key_path, "wb") as dst:
                    dst.write(pub_data)
        except Exception as exc:
            logger.warning("Could not mirror public key: %s", exc)

        try:
            os.chmod(self.private_key_path, 0o600)
        except Exception:
            pass

        # Populate the in-memory handles so callers don't have to reload.
        self._private_key = private_key
        self._public_key = public_key
        logger.info("Generated new RSA-2048 keypair for license signing.")

    def _get_private_key(self):
        if self._private_key is None:
            self._load_or_create_keys()
        return self._private_key

    def _get_public_key(self):
        if self._public_key is None:
            self._load_or_create_keys()
        return self._public_key

    # ------------------------------------------------------- signing helpers
    def _canonical_payload(self, payload: dict) -> bytes:
        """Deterministic serialisation so signatures are stable across runs."""
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _sign(self, payload: dict) -> str:
        key = self._get_private_key()
        signature = key.sign(
            self._canonical_payload(payload),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.urlsafe_b64encode(signature).decode("ascii")

    @staticmethod
    def _machine_digest(machine_id: str) -> str:
        """Salted digest so the raw machine id never travels in the license."""
        return hashlib.sha256(
            (machine_id + "::machine-lock-v1").encode("utf-8")
        ).hexdigest()
# ------------------------------------------------------- license creation
    def generate_license(self, tier: str = LicenseTier.BASIC,
                         machine_id: str | None = None,
                         duration_days: int | None = None,
                         license_uuid: str | None = None,
                         customer_email: str = "",
                         issued_at: str | None = None) -> dict:
        """
        Generate a signed license for a given tier and machine.

        ``duration_days`` overrides the plan's default when provided (used to
        grant the exact paid duration, or a lifetime for Elite).
        """
        if tier != LicenseTier.TRIAL and tier not in PLANS:
            raise ValueError(f"Unknown license tier: {tier}")

        if duration_days is None:
            if tier == LicenseTier.TRIAL:
                duration_days = 7
            else:
                duration_days = PLANS[tier].duration_days

        if tier == LicenseTier.ELITE:
            duration_days = MAX_LICENSE_DAYS  # lifetime updates perk

        if duration_days <= 0 or duration_days > MAX_LICENSE_DAYS:
            raise ValueError("duration_days out of acceptable range")

        now = datetime.now(timezone.utc)
        issued = issued_at or now.isoformat()
        exp = now + timedelta(days=duration_days)

        machine = machine_id or self.machine_id
        payload = {
            "v": PAYLOAD_VERSION,
            "uuid": license_uuid or str(uuid.uuid4()),
            "tier": tier,
            "machine": self._machine_digest(machine),
            "issued": issued,
            "expires": exp.isoformat(),
            "duration_days": duration_days,
            "email": (customer_email or "").lower(),
            "lifetime": bool(duration_days >= MAX_LICENSE_DAYS),
        }
        payload["sig"] = self._sign(payload)
        return payload

    def human_license_key(self, payload: dict) -> str:
        """
        Render a license as an installable, dashed key string (PHX-...).

        This is LOSSLESS: we base64-encode the entire signed payload (including
        the signature) and chunk it, so decoding returns the exact payload that
        can then be RSA-verified offline.
        """
        raw = base64.urlsafe_b64encode(
            self._canonical_payload(payload)
        ).decode("ascii").rstrip("=")
        key = "PHX-" + "-".join(
            [raw[i:i + 5] for i in range(0, len(raw), 5)]
        )
        return key

    @staticmethod
    def decode_license_key(key: str) -> dict:
        """Convert a display key (PHX-...) back into a license dict."""
        cleaned = key.strip()
        if cleaned.upper().startswith("PHX-"):
            cleaned = cleaned[4:]
        elif cleaned.upper().startswith("PHX"):
            cleaned = cleaned[3:]
        raw = re.sub(r"[^A-Za-z0-9_-]", "", cleaned)
        raw = re.sub(r"-", "", raw)
        padding = (4 - len(raw) % 4) % 4
        raw += "=" * padding
        try:
            decoded = base64.urlsafe_b64decode(raw)
        except Exception as exc:
            raise ValueError(f"License key is not valid base64: {exc}")
        try:
            payload = json.loads(decoded.decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"License key payload is malformed: {exc}")
        if not isinstance(payload, dict) or "sig" not in payload:
            raise ValueError("License key is missing its signature")
        return payload
# ------------------------------------------------------- license validation
    def verify_signature(self, payload: dict) -> bool:
        """Verify the RSA signature over a payload's canonical body."""
        sig_b64 = payload.get("sig", "")
        # Drop 'sig' so we re-sign exactly the body that was signed.
        body = {k: v for k, v in payload.items() if k != "sig"}
        try:
            signature = base64.urlsafe_b64decode(sig_b64)
            self._get_public_key().verify(
                signature,
                self._canonical_payload(body),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception as exc:
            logger.warning("License signature verification failed: %s", exc)
            return False

    @staticmethod
    def parse_expiry(payload: dict):
        """Return the expires value as an aware datetime, or None if missing."""
        raw = payload.get("expires")
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def validate(self, payload: dict, force_offline: bool = True) -> dict:
        """
        Validate a license payload. Returns:
            {valid, status, tier, expires_at, remaining_days, reason}

        Offline validation checks signature, structure, expiry and machine
        binding. When ``force_offline`` is False and online validation is
        enabled, the result is cross-checked via the payment server.
        """
        result = {
            "valid": False,
            "status": LicenseStatus.INVALID,
            "tier": payload.get("tier", "unknown"),
            "expires_at": payload.get("expires"),
            "remaining_days": None,
            "reason": "Unknown error",
        }

        # 1) Structural sanity
        if payload.get("v", 0) != PAYLOAD_VERSION:
            result["reason"] = f"Unsupported license version: {payload.get('v')}"
            return result
        tier = payload.get("tier")
        if tier not in (LicenseTier.BASIC, LicenseTier.PRO,
                        LicenseTier.ELITE, LicenseTier.TRIAL):
            result["reason"] = f"Unknown license tier: {tier}"
            return result

        # 2) Cryptographic signature
        if not self.verify_signature(payload):
            result["reason"] = "License signature is invalid or tampered"
            return result

        # 3) Expiry
        exp = self.parse_expiry(payload)
        if exp is None:
            result["reason"] = "License has no valid expiry"
            return result
        remaining = (exp - datetime.now(timezone.utc)).total_seconds() / 86400.0
        result["remaining_days"] = round(remaining, 2)
        if remaining <= 0:
            result["status"] = LicenseStatus.EXPIRED
            result["reason"] = "License has expired"
            return result

        # 4) Hardware binding
        expected = payload.get("machine", "")
        actual = self._machine_digest(self.machine_id)
        if expected and expected != actual:
            result["status"] = LicenseStatus.HARDWARE_MISMATCH
            result["reason"] = "License is bound to a different machine"
            return result

        # 5) Optional online cross-check
        if not force_offline and CONFIG.allow_online_validation:
            online = self._validate_online(payload)
            if online is not None and not online.get("valid", False):
                result["status"] = online.get("status", LicenseStatus.INVALID)
                result["reason"] = online.get("reason", "Online validation failed")
                return result

        result["valid"] = True
        result["status"] = LicenseStatus.ACTIVE
        result["reason"] = "License is active and valid"
        return result

    def _validate_online(self, payload: dict) -> dict | None:
        """Best-effort online confirmation via the payment server."""
        try:
            import requests
            url = f"{CONFIG.base_url}/api/verify-license"
            resp = requests.post(
                url, json={"key": self.human_license_key(payload)}, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                return {"valid": bool(data.get("valid", False)),
                        "status": data.get("status"),
                        "reason": data.get("reason", "")}
        except Exception as exc:
            logger.warning("Online license validation unavailable: %s", exc)
        return None
# ------------------------------------------------------- storage & activate
    def _storage_key(self) -> bytes:
        """Derive a per-machine Fernet key for encrypting the stored license."""
        import base64 as _b64
        digest = hashlib.sha256(self.machine_id.encode("utf-8")).digest()
        return _b64.urlsafe_b64encode(digest)

    def activate(self, license_key: str, persist: bool = True) -> dict:
        """Decode + validate a user-supplied key and store it persistently."""
        payload = self.decode_license_key(license_key)
        result = self.validate(payload)
        if result["valid"] and persist:
            try:
                from utils.cryptor import Cryptor
                crypt = Cryptor(key=self._storage_key())
                os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
                # Write atomically to avoid partial license files.
                tmp = LICENSE_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write(crypt.encrypt(license_key))
                os.replace(tmp, LICENSE_FILE)
                logger.info("License activated and stored at %s", LICENSE_FILE)
            except Exception as exc:
                logger.error("Failed to persist license: %s", exc)
                result = dict(result)
                result["reason"] += " (persist failed)"
        result["payload"] = payload
        return result

    def load_stored(self) -> dict | None:
        """Load the encrypted, stored license and return its decoded payload."""
        if not os.path.exists(LICENSE_FILE):
            return None
        try:
            from utils.cryptor import Cryptor
            crypt = Cryptor(key=self._storage_key())
            with open(LICENSE_FILE, "r", encoding="utf-8") as fh:
                key = crypt.decrypt(fh.read().strip())
            return self.decode_license_key(key)
        except Exception as exc:
            logger.warning("Could not load stored license: %s", exc)
            return None

    def clear_stored(self) -> None:
        if os.path.exists(LICENSE_FILE):
            try:
                os.remove(LICENSE_FILE)
            except Exception:
                pass

    def create_trial(self, persist: bool = False) -> dict:
        """Generate a short trial license for demo/testing."""
        payload = self.generate_license(
            tier=LicenseTier.TRIAL, duration_days=7,
            customer_email="trial@local",
        )
        return self.activate(self.human_license_key(payload), persist=persist)


# ---------------------------------------------------------------------------
# Module-level helpers (backwards-friendly defaults)
# ---------------------------------------------------------------------------
def default_manager() -> LicenseManager:
    """Return a shared, default LicenseManager (generates keys on first use)."""
    return LicenseManager()