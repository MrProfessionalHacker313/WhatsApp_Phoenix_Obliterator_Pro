"""
PHOENIX EAGLE — SHARE PACKAGE BUILDER
=====================================
Bundles the Phoenix Engine plus an embedded license into a single, self-
extracting executable and uploads it to permanent cloud storage so every
share link can offer a *direct* download.

Pipeline
--------
1.  Generate an embedded license (an unbound license for the target plan).
2.  Write a minimal ``embedded_license.json`` payload next to the source and a
    boot-stub that reads it and injects it as the active license on first run.
3.  Invoke PyInstaller to build a single ``--onefile`` executable.
4.  Upload the built executable to IPFS (Pinata gateway) or an S3-compatible
    bucket (boto3).
5.  Attach the returned permanent download URL to the share link record and
    return it.

Cloud providers
---------------
* IPFS via the Pinata REST gateway when ``PINATA_API_KEY``/``PINATA_SECRET``
  are set. Returns a gateway URL.
* S3 via boto3 when ``S3_BUCKET``/``AWS_ACCESS_KEY_ID``/``AWS_SECRET_ACCESS_KEY``
  are set. Returns a (pre-signed-safe) object URL.

If neither provider is configured, the module falls back to copying the built
executable into a local ``dist/`` folder and returns a ``file://`` link so the
pipeline remains fully testable offline.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from payment.config import PLANS

from .link_generator import ShareLinkGenerator
from .storage import ASSETS

logger = logging.getLogger("phoenix.sharing.build")

# The directory whose source is bundled into the executable.
PYTHON_CORE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _craft_asset_id() -> str:
    return f"asset_{uuid.uuid4().hex[:16]}"


# ---------------------------------------------------------------------------
# Embedded license + boot stub authoring
# ---------------------------------------------------------------------------
def _write_embedded_license(record: dict, workdir: str) -> str:
    """
    Persist the share link's signed license as an embedded payload the bundled
    boot stub will auto-activate. Returns the path to the payload file.
    """
    license_key = record.get("license_key", "")
    payload_file = os.path.join(workdir, "embedded_license.json")
    with open(payload_file, "w", encoding="utf-8") as fh:
        json.dump({
            "license_key": license_key,
            "ref": record.get("ref", ""),
            "tier": record.get("plan", "basic"),
            "product": "Phoenix Eagle Ultra Pro",
            "generated": _now(),
        }, fh, indent=2)
    return payload_file


BOOT_STUB = r'''
# -*- coding: utf-8 -*-
"""Boot stub bundled into the share executable.

On first run it locates ``embedded_license.json`` that ships next to the
binary, validates the embedded license offline, and activates it so the
recipient has instant full access. This keeps the bundled copy per-link while
re-using the canonical payment/license_manager verification path.
"""
import json
import os
import sys

EMBEDDED_NAME = "embedded_license.json"


def _locate_embedded():
    # In a PyInstaller --onefile build the payload is unpacked to sys._MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = os.path.join(meipass, EMBEDDED_NAME)
        if os.path.exists(candidate):
            return candidate
    # Fallbacks: next to the binary, or the frozen extraction dir.
    for base in (os.path.dirname(sys.executable),
                 os.path.dirname(os.path.abspath(__file__))):
        candidate = os.path.join(base, EMBEDDED_NAME)
        if os.path.exists(candidate):
            return candidate
    return None


def main():
    embedded = _locate_embedded()
    if embedded:
        try:
            with open(embedded, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            key = payload.get("license_key", "")
            if key:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from payment.license_manager import LicenseManager
                from utils.license_validator import get_validator
                mgr = LicenseManager()
                decoded = mgr.decode_license_key(key)
                result = mgr.validate(decoded, force_offline=True)
                if result["valid"]:
                    get_validator().activate(key)
                    print(f"[Phoenix Eagle] Embedded license {payload.get('ref', '')} activated.")
                else:
                    print(f"[Phoenix Eagle] Embedded license invalid: {result['reason']}")
        except Exception as exc:  # non-fatal: engine still runs in demo mode
            print(f"[Phoenix Eagle] Could not auto-activate embedded license: {exc}")

    # Launch the real CLI entry point if present, else a friendly banner.
    main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    if os.path.exists(main_py):
        sys.path.insert(0, os.path.dirname(main_py))
        import runpy
        runpy.run_path(main_py, run_name="__main__")
    else:
        print("Phoenix Eagle Ultra Pro - run the main engine from source.")


if __name__ == "__main__":
    main()
'''
# ===========================================================================
# Build orchestration
# ===========================================================================
class SharePackageBuilder:
    """Builds an executable for a share link and attaches its download URL."""

    def __init__(self, generator: ShareLinkGenerator | None = None,
                 assets_store=ASSETS):
        self.generator = generator or ShareLinkGenerator()
        self.assets = assets_store

    # ------------------------------------------------------------- top level
    def build_package(self, ref_code: str, plan_key: str = "basic",
                      out_dir: str | None = None) -> dict:
        """
        Build + upload the downloadable package for a share link.

        Returns the asset record: {asset_id, ref, build_status, download_url,
        provider, artifact, built_at}.
        """
        record = self.generator.get(ref_code)
        if not record:
            raise ValueError(f"Unknown share link: {ref_code}")
        if plan_key != record.get("plan"):
            plan_key = record.get("plan", "basic")

        workdir = tempfile.mkdtemp(prefix="phoenix_share_")
        try:
            embedded = _write_embedded_license(record, workdir)
            artifact_path = self._run_pyinstaller(workdir, embedded, out_dir)
            download_url, provider = self._upload(artifact_path, ref_code)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        asset_id = _craft_asset_id()
        asset = {
            "asset_id": asset_id,
            "ref": ref_code,
            "plan": plan_key,
            "build_status": "ready",
            "download_url": download_url,
            "provider": provider,
            "artifact": artifact_path,
            "built_at": _now(),
        }
        self.assets.set(asset_id, asset)

        # Attach the permanent download link to the share link record.
        self.generator.store.mutate(ref_code, lambda rec: {
            **rec, "download_url": download_url, "asset_id": asset_id})

        logger.info("Built+uploaded package %s for ref %s (%s)",
                    artifact_path, ref_code, provider)
        return asset
    # -------------------------------------------------------------- build
    def _run_pyinstaller(self, workdir: str, embedded: str,
                         out_dir: str | None) -> str:
        """Run PyInstaller to produce a single, self-contained executable."""
        try:
            import PyInstaller.__main__ as pyi
        except Exception:
            raise RuntimeError(
                "PyInstaller is not installed. Install with: pip install pyinstaller")

        dist = out_dir or os.path.join(PYTHON_CORE, "sharing", "dist")
        os.makedirs(dist, exist_ok=True)
        bundle_name = f"PhoenixEagle_{time.strftime('%Y%m%d_%H%M%S')}"

        # A tiny wrapper that the boot stub checks; the stub expects to find the
        # embedded payload in the frozen package under this exact name.
        package_dir = os.path.join(workdir, "bundle")
        os.makedirs(package_dir, exist_ok=True)
        stub_path = os.path.join(package_dir, "phoenix_boot.py")
        with open(stub_path, "w", encoding="utf-8") as fh:
            fh.write(BOOT_STUB)
        shutil.copy2(embedded, os.path.join(package_dir, "embedded_license.json"))

        entry = os.path.join(package_dir, "phoenix_boot.py")
        args = [
            entry,
            "--name", bundle_name,
            "--onefile",
            "--distpath", dist,
            "--workpath", os.path.join(workdir, "build"),
            "--specpath", os.path.join(workdir),
            "--add-data",
            f"{os.path.join(package_dir, 'embedded_license.json')}{os.pathsep}.",
            "--hidden-import", "payment.config",
            "--hidden-import", "payment.license_manager",
            "--hidden-import", "utils.license_validator",
            "--hidden-import", "cryptography",
        ]
        try:
            pyi.run(args)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise RuntimeError(f"PyInstaller exited with {exc.code}")

        artifact = os.path.join(dist, f"{bundle_name}.exe" if os.name == "nt"
                                else bundle_name)
        if not os.path.exists(artifact):
            raise RuntimeError("PyInstaller did not produce the expected artifact")
        return artifact
    # ------------------------------------------------------------- upload
    def _upload(self, artifact_path: str, ref_code: str) -> tuple[str, str]:
        """Upload the artifact; returns (download_url, provider)."""
        if _ipfs_configured():
            url = self._upload_ipfs(artifact_path, ref_code)
            return url, "ipfs"
        if _s3_configured():
            return self._upload_s3(artifact_path, ref_code), "s3"
        # Offline fallback: keep a local copy and return a file:// URL so the
        # pipeline stays fully testable offline (permanent on the local host).
        local = os.path.join(PYTHON_CORE, "sharing", "dist",
                             os.path.basename(artifact_path))
        os.makedirs(os.path.dirname(local), exist_ok=True)
        shutil.copy2(artifact_path, local)
        return f"file://{local}", "local"

    def _upload_ipfs(self, artifact_path: str, ref_code: str) -> str:
        """Upload via the Pinata REST API; returns a permanent gateway URL."""
        import requests
        api_key = os.environ.get("PINATA_API_KEY", "").strip()
        api_secret = os.environ.get("PINATA_SECRET", "").strip()
        gateway = os.environ.get("IPFS_GATEWAY",
                                 "https://gateway.pinata.cloud").rstrip("/")
        with open(artifact_path, "rb") as fh:
            resp = requests.post(
                "https://api.pinata.cloud/pinning/pinFileToIPFS",
                headers={"pinata_api_key": api_key,
                         "pinata_secret_api_key": api_secret},
                files={"file": (os.path.basename(artifact_path), fh)},
                data={"pinataMetadata": json.dumps({"name": ref_code})},
                timeout=300,
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Pinata upload failed: {resp.status_code} {resp.text}")
        cid = resp.json().get("IpfsHash")
        return f"{gateway}/ipfs/{cid}"

    def _upload_s3(self, artifact_path: str, ref_code: str) -> str:
        """Upload via boto3 to an S3-compatible bucket; return the object URL."""
        import boto3
        bucket = os.environ.get("S3_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError("S3_BUCKET is not configured")
        key = f"phoenix-shares/{ref_code}/{os.path.basename(artifact_path)}"
        client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("S3_ENDPOINT") or None,
        )
        client.upload_file(artifact_path, bucket, key)
        endpoint = os.environ.get("S3_ENDPOINT", "").rstrip("/")
        if endpoint:
            return f"{endpoint}/{bucket}/{key}"
        region = os.environ.get("AWS_REGION", "us-east-1")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def _ipfs_configured() -> bool:
    return bool(os.environ.get("PINATA_API_KEY")
                and os.environ.get("PINATA_SECRET"))


def _s3_configured() -> bool:
    return bool(os.environ.get("S3_BUCKET"))


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """Command-line wrapper: ``python sharing/build_package.py <ref> [plan]``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("Usage: python sharing/build_package.py <ref_code> [plan_key]")
        return 1
    ref = argv[0]
    plan = argv[1] if len(argv) > 1 else "basic"
    try:
        asset = SharePackageBuilder().build_package(ref_code=ref, plan_key=plan)
        print(f"\n[OK] Package built + uploaded")
        print(f"     Ref       : {asset['ref']}")
        print(f"     Provider  : {asset['provider']}")
        print(f"     Download  : {asset['download_url']}")
        return 0
    except Exception as exc:
        print(f"[ERR] {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
