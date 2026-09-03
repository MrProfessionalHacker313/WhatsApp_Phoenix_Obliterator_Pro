#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║   🦅 PHOENIX OBLITERATOR PRO — MASTER LAUNCHER v3.0       ║
║   All-in-One Command Center                                 ║
║   Integrates: CLI · Payment · Node Bridge · Web · Mobile    ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python run.py

From the project root, this launcher starts every component of the
WhatsApp Phoenix Obliterator Pro stack:
  • Phoenix Engine CLI        (backend/python_core/main.py)
  • Payment / License Server  (Flask, port 8787)
  • Node WhatsApp Bridge      (backend/node_whatsapp/server.js)
  • Web SOC Dashboard         (web_interface/dashboard.html)
  • Mobile App helper         (Expo, React Native)
  • Share Package Builder     (PyInstaller + IPFS/S3)
  • System Diagnostics
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# Paths (resolved from THIS file's location = project root)
# ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
PYTHON_CORE = ROOT / "backend" / "python_core"
NODE_BRIDGE = ROOT / "backend" / "node_whatsapp"
WEB_DIR = ROOT / "web_interface"
MOBILE_DIR = ROOT / "mobile_app"
REQUIREMENTS = PYTHON_CORE / "requirements.txt"

# ──────────────────────────────────────────────────────────────────────
# ANSI colour helpers (pure ANSI, no external deps)
# ──────────────────────────────────────────────────────────────────────
class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[90m"
    GOLD = "\033[93m"
    FIRE = "\033[91m"
    STEEL = "\033[94m"
    WHITE = "\033[97m"
    GREEN = "\033[92m"
    BG_BLK = "\033[40m"

def _color_ok() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return bool(getattr(sys.stdout, "isatty", lambda: False)())
    except Exception:
        return True

_COLOR = _color_ok()

def c(text: str, code: str = _C.GOLD) -> str:
    return f"{code}{text}{_C.RESET}" if _COLOR else text

# ──────────────────────────────────────────────────────────────────────
# Screen helpers
# ──────────────────────────────────────────────────────────────────────
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def banner(title: str = "MASTER LAUNCHER", subtitle: str = "All-in-One Command Center"):
    clear()
    w = 56
    print(c(f"\n   ┌{'─' * w}┐", _C.GOLD))
    print(c(f"   │{title.center(w)}│", _C.GOLD))
    print(c(f"   │{subtitle.center(w)}│", _C.DIM))
    print(c(f"   └{'─' * w}┘\n", _C.GOLD))

def section(text: str):
    print()
    print(c(f"   🦅  {text}  🦅", _C.STEEL))
    print(c(f"      {'═' * 44}", _C.STEEL))

def divider(color=_C.FIRE, glyph="▓"):
    inner = glyph * 44
    print(c(f"   🦅 {inner} 🦅", color))

def status_line(label: str, value: str, label_color=_C.STEEL, val_color=_C.WHITE):
    print("   " + c(f"[{label}]", label_color) + c("  ▸  ", _C.DIM) + c(value, val_color))

def ok(msg: str):
    print("   " + c("✓", _C.GREEN) + " " + c(msg, _C.WHITE))

def fail(msg: str):
    print("   " + c("✗", _C.FIRE) + " " + c(msg, _C.FIRE))

def warn(msg: str):
    print("   " + c("⚠", _C.GOLD) + " " + c(msg, _C.GOLD))

def info(msg: str):
    print("   " + c("ℹ", _C.STEEL) + " " + c(msg, _C.WHITE))

def prompt_input(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(c(f"\n   [+] {label}{suffix}: ", _C.STEEL)).strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return val if val else default

# ──────────────────────────────────────────────────────────────────────
# Pre-flight diagnostics
# ──────────────────────────────────────────────────────────────────────
def run_diagnostics() -> dict:
    section("SYSTEM DIAGNOSTICS")
    results: dict = {}

    # Python
    py_ver = f"{sys.version.split()[0]} ({platform.architecture()[0]})"
    results["python"] = {"ok": True, "info": py_ver}
    ok(f"Python {py_ver}")

    # OS
    os_name = f"{platform.system()} {platform.release()}"
    results["os"] = {"ok": True, "info": os_name}
    ok(f"OS: {os_name}")

    # pip
    pip_path = shutil.which("pip") or shutil.which("pip3")
    if pip_path:
        try:
            pv = subprocess.run(
                [pip_path, "--version"], capture_output=True, text=True, timeout=10
            ).stdout.strip()
            results["pip"] = {"ok": True, "info": pv}
            ok(f"pip: {pv}")
        except Exception as exc:
            results["pip"] = {"ok": False, "info": str(exc)}
            fail(f"pip: {exc}")
    else:
        results["pip"] = {"ok": False, "info": "not found"}
        fail("pip not found")

    # node
    node_path = shutil.which("node")
    if node_path:
        try:
            nv = subprocess.run(
                [node_path, "--version"], capture_output=True, text=True, timeout=10
            ).stdout.strip()
            results["node"] = {"ok": True, "info": nv}
            ok(f"Node.js {nv}")
        except Exception as exc:
            results["node"] = {"ok": False, "info": str(exc)}
            fail(f"Node.js: {exc}")
    else:
        results["node"] = {"ok": False, "info": "not found"}
        warn("Node.js not found — bridge unavailable")

    # npm
    npm_path = shutil.which("npm")
    if npm_path:
        try:
            npmv = subprocess.run(
                [npm_path, "--version"], capture_output=True, text=True, timeout=10
            ).stdout.strip()
            results["npm"] = {"ok": True, "info": npmv}
            ok(f"npm {npmv}")
        except Exception as exc:
            results["npm"] = {"ok": False, "info": str(exc)}
            fail(f"npm: {exc}")
    else:
        results["npm"] = {"ok": False, "info": "not found"}
        warn("npm not found — bridge unavailable")

    # Playwright (optional)
    try:
        import playwright  # noqa: F401
        results["playwright"] = {"ok": True, "info": "installed"}
        ok("Playwright: installed")
    except ImportError:
        results["playwright"] = {"ok": False, "info": "not installed"}
        warn("Playwright not installed (optional)")

    # Flask (payment server dependency)
    try:
        import flask  # noqa: F401
        results["flask"] = {"ok": True, "info": flask.__version__}
        ok(f"Flask {flask.__version__}")
    except ImportError:
        results["flask"] = {"ok": False, "info": "not installed"}
        fail("Flask not installed — payment server unavailable")

    # Project directories
    for name, pth in [
        ("python_core", PYTHON_CORE),
        ("node_bridge", NODE_BRIDGE),
        ("web_interface", WEB_DIR),
        ("mobile_app", MOBILE_DIR),
    ]:
        exists = pth.is_dir()
        results[name] = {"ok": exists, "info": str(pth)}
        if exists:
            ok(f"{name}: {pth}")
        else:
            fail(f"{name} missing: {pth}")

    # Virtual environment
    venv_candidates = [
        ROOT / ".venv",
        PYTHON_CORE / ".venv",
        PYTHON_CORE.parent / ".venv",
    ]
    venv_found = any(v.is_dir() for v in venv_candidates)
    results["venv"] = {"ok": venv_found, "info": str([str(v) for v in venv_candidates if v.is_dir()])}
    if venv_found:
        ok("Virtual environment detected")
    else:
        warn("No .venv found — using system Python")

    print()
    return results

# ──────────────────────────────────────────────────────────────────────
# Module: Phoenix Engine CLI
# ──────────────────────────────────────────────────────────────────────
def start_cli():
    section("PHOENIX ENGINE CLI")
    main_py = PYTHON_CORE / "main.py"
    if not main_py.is_file():
        fail(f"main.py not found at {main_py}")
        return
    ok(f"Launching: {main_py}")
    print()
    try:
        subprocess.run(
            [sys.executable, str(main_py)],
            cwd=str(PYTHON_CORE),
            check=False,
        )
    except KeyboardInterrupt:
        warn("CLI interrupted by user")
    print()

# ──────────────────────────────────────────────────────────────────────
# Module: Payment / License Server (Flask)
# ──────────────────────────────────────────────────────────────────────
def start_payment_server():
    section("PAYMENT / LICENSE SERVER")
    payment_server = PYTHON_CORE / "payment" / "payment_server.py"
    if not payment_server.is_file():
        fail(f"payment_server.py not found at {payment_server}")
        return
    try:
        from payment.config import CONFIG, PaymentConfig
        host = CONFIG.server_host
        port = CONFIG.server_port
    except Exception:
        host = "127.0.0.1"
        port = 8787
    ok(f"Flask server starting on http://{host}:{port}")
    info(f"Checkout: http://{host}:{port}/checkout/checkout.html")
    info("Press Ctrl+C to stop the server.\n")
    try:
        # Run in-process so Flask's reloader doesn't spawn a child that
        # outlives this menu loop.
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PYTHON_CORE)
        subprocess.run(
            [sys.executable, "-m", "payment.payment_server"],
            cwd=str(PYTHON_CORE),
            env=env,
            check=False,
        )
    except KeyboardInterrupt:
        warn("Payment server stopped")
    print()

# ──────────────────────────────────────────────────────────────────────
# Module: Node.js WhatsApp Bridge
# ──────────────────────────────────────────────────────────────────────
def start_node_bridge():
    section("NODE.JS WHATSAPP BRIDGE")
    server_js = NODE_BRIDGE / "server.js"
    if not server_js.is_file():
        fail(f"server.js not found at {server_js}")
        return
    node_path = shutil.which("node")
    if not node_path:
        fail("Node.js binary not found in PATH")
        return
    ok(f"Node bridge starting: {server_js}")
    info(f"Working directory: {NODE_BRIDGE}")
    info("Press Ctrl+C to stop the bridge.\n")
    try:
        subprocess.run(
            [node_path, str(server_js)],
            cwd=str(NODE_BRIDGE),
            check=False,
        )
    except KeyboardInterrupt:
        warn("Node bridge stopped")
    print()

# ──────────────────────────────────────────────────────────────────────
# Module: Web SOC Dashboard
# ──────────────────────────────────────────────────────────────────────
def open_web_dashboard():
    section("WEB SOC DASHBOARD")
    dashboard = WEB_DIR / "dashboard.html"
    if not dashboard.is_file():
        fail(f"dashboard.html not found at {dashboard}")
        input(c("\n   [ PRESS ENTER ]", _C.STEEL))
        return
    url = dashboard.resolve().as_uri()
    ok(f"Opening dashboard: {url}")
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception as exc:
        fail(f"Could not open browser: {exc}")
        info(f"Open manually: {url}")
    print()
    time.sleep(1.5)

# ──────────────────────────────────────────────────────────────────────
# Module: Mobile App (Expo helper)
# ──────────────────────────────────────────────────────────────────────
def mobile_app_helper():
    section("MOBILE APP (React Native / Expo)")
    app_js = MOBILE_DIR / "App.js"
    if not app_js.is_file():
        fail("Mobile app files not found")
        info(f"Expected at: {MOBILE_DIR}")
        return
    ok(f"Mobile app detected at: {MOBILE_DIR}")
    print()
    print(c("   Available commands:", _C.STEEL))
    print(c("   1. npm start        — Expo dev server", _C.WHITE))
    print(c("   2. npm run android  — Android emulator", _C.WHITE))
    print(c("   3. npm run ios      — iOS simulator", _C.WHITE))
    print(c("   4. npm run web      — Web preview", _C.WHITE))
    print(c("   0. Back", _C.DIM))
    choice = prompt_input("Select").strip()
    commands = {
        "1": ["npm", "start"],
        "2": ["npm", "run", "android"],
        "3": ["npm", "run", "ios"],
        "4": ["npm", "run", "web"],
    }
    if choice in commands:
        npm = shutil.which("npm")
        if not npm:
            fail("npm not found")
            return
        ok(f"Running: {' '.join(commands[choice])}")
        print()
        try:
            subprocess.run(
                commands[choice],
                cwd=str(MOBILE_DIR),
                check=False,
            )
        except KeyboardInterrupt:
            warn("Mobile command interrupted")
        print()

# ──────────────────────────────────────────────────────────────────────
# Module: Install Dependencies
# ──────────────────────────────────────────────────────────────────────
def install_dependencies():
    section("INSTALL DEPENDENCIES")
    print()
    print(c("   [1] Python dependencies  (pip install -r requirements.txt)", _C.WHITE))
    print(c("   [2] Node bridge deps    (npm install --prefix backend/node_whatsapp)", _C.WHITE))
    print(c("   [3] Playwright browsers (playwright install chromium)", _C.WHITE))
    print(c("   [4] ALL of the above", _C.GOLD))
    print(c("   [0] Back", _C.DIM))
    choice = prompt_input("Select").strip()

    if choice in ("1", "4"):
        pip = shutil.which("pip") or shutil.which("pip3")
        if not pip:
            fail("pip not found")
        else:
            ok(f"Installing Python deps from {REQUIREMENTS}")
            subprocess.run(
                [pip, "install", "-r", str(REQUIREMENTS)],
                cwd=str(ROOT),
                check=False,
            )
            ok("Python dependencies installed")

    if choice in ("2", "4"):
        npm = shutil.which("npm")
        if not npm:
            fail("npm not found")
        else:
            ok("Installing Node bridge dependencies")
            subprocess.run(
                ["npm", "install"],
                cwd=str(NODE_BRIDGE),
                check=False,
            )
            ok("Node dependencies installed")

    if choice in ("3", "4"):
        try:
            ok("Installing Playwright Chromium browser")
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                cwd=str(PYTHON_CORE),
                check=False,
            )
            ok("Playwright Chromium installed")
        except Exception as exc:
            fail(f"Playwright install failed: {exc}")

    print()

# ──────────────────────────────────────────────────────────────────────
# Module: Build Share Package
# ──────────────────────────────────────────────────────────────────────
def build_share_package():
    section("BUILD SHARE PACKAGE")
    print()
    ref = prompt_input("Enter share link ref code (PHX-XXXX-XXXX)", "PHX-AAAA-BBBB")
    plan = prompt_input("Plan key (basic / pro / elite)", "basic")
    print()
    ok(f"Building package for ref={ref} plan={plan}")
    info("This requires PyInstaller. Falling back to local dist if unavailable.")
    print()
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PYTHON_CORE)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "sharing.build_package",
                ref,
                plan,
            ],
            cwd=str(PYTHON_CORE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            ok("Build completed successfully")
            print(c(f"   {result.stdout.strip()}", _C.DIM))
        else:
            fail(f"Build failed (exit {result.returncode})")
            if result.stderr:
                print(c(f"   {result.stderr.strip()}", _C.FIRE))
    except Exception as exc:
        fail(f"Could not run build_package: {exc}")
    print()

# ──────────────────────────────────────────────────────────────────────
# Module: Owner Management
# ──────────────────────────────────────────────────────────────────────
def owner_management():
    section("OWNER MANAGEMENT")
    print()
    print(c("   [1] Activate Owner Mode", _C.WHITE))
    print(c("   [2] Generate Free License Key", _C.WHITE))
    print(c("   [3] List Generated Keys", _C.WHITE))
    print(c("   [4] Check Owner Status", _C.WHITE))
    print(c("   [5] Deactivate Owner Mode", _C.WHITE))
    print(c("   [0] Back", _C.DIM))
    choice = prompt_input("Select").strip()
    print()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PYTHON_CORE)

    if choice == "1":
        key = prompt_input("Enter master key").strip()
        if not key:
            return
        ok("Activating owner mode...")
        result = subprocess.run(
            [sys.executable, "-c",
             f"from payment.owner_access import get_owner; "
             f"r = get_owner().activate('{key}'); "
             f"print('SUCCESS' if r['success'] else 'FAILED: ' + r.get('reason',''))"],
            cwd=str(PYTHON_CORE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        out = (result.stdout or result.stderr).strip()
        if "SUCCESS" in out.upper():
            ok(out)
        else:
            fail(out or "Unknown error")
    elif choice == "2":
        tier = prompt_input("Tier (basic / pro / elite / trial)", "pro").strip().lower()
        days = prompt_input("Duration (days or 'lifetime')", "30").strip()
        ok("Generating key...")
        result = subprocess.run(
            [sys.executable, "-c",
             f"from payment.owner_access import get_owner; "
             f"r = get_owner().genkey('{tier}', '{days}'); "
             f"print(r.get('key','') if r.get('success') else 'FAILED: ' + r.get('reason',''))"],
            cwd=str(PYTHON_CORE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        out = (result.stdout or result.stderr).strip()
        if out and "FAILED" not in out.upper():
            ok(f"Generated key: {out}")
        else:
            fail(out or "Unknown error")
    elif choice == "3":
        result = subprocess.run(
            [sys.executable, "-c",
             "from payment.owner_access import get_owner; "
             "import json; keys = get_owner().list_keys(); "
             "print(json.dumps(keys, indent=2))"],
            cwd=str(PYTHON_CORE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        out = (result.stdout or result.stderr).strip()
        print(c(f"   {out}", _C.WHITE))
    elif choice == "4":
        result = subprocess.run(
            [sys.executable, "-c",
             "from payment.owner_access import get_owner; "
             "import json; print(json.dumps(get_owner().status(), indent=2))"],
            cwd=str(PYTHON_CORE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        out = (result.stdout or result.stderr).strip()
        print(c(f"   {out}", _C.WHITE))
    elif choice == "5":
        confirm = prompt_input("Type DEACTIVATE to confirm", "").strip()
        if confirm == "DEACTIVATE":
            result = subprocess.run(
                [sys.executable, "-c",
                 "from payment.owner_access import get_owner; "
                 "r = get_owner().deactivate(); "
                 "print('SUCCESS' if r['success'] else 'FAILED: ' + r.get('reason',''))"],
                cwd=str(PYTHON_CORE),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            out = (result.stdout or result.stderr).strip()
            if "SUCCESS" in out.upper():
                ok(out)
            else:
                fail(out or "Unknown error")
        else:
            warn("Deactivation cancelled")
    print()

# ──────────────────────────────────────────────────────────────────────
# Module: License Management helper
# ──────────────────────────────────────────────────────────────────────
def license_management():
    section("LICENSE MANAGEMENT")
    print()
    print(c("   [1] Activate License Key", _C.WHITE))
    print(c("   [2] Check License Status", _C.WHITE))
    print(c("   [3] View Pricing Plans", _C.WHITE))
    print(c("   [4] Owner Management", _C.WHITE))
    print(c("   [0] Back", _C.DIM))
    choice = prompt_input("Select").strip()
    print()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PYTHON_CORE)

    if choice == "1":
        key = prompt_input("Enter license key").strip()
        if not key:
            return
        ok("Activating license...")
        result = subprocess.run(
            [sys.executable, "-c",
             f"from utils.license_validator import get_validator; "
             f"r = get_validator().activate('{key}'); "
             f"print('VALID' if r['valid'] else 'INVALID: ' + r.get('reason',''))"],
            cwd=str(PYTHON_CORE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        out = (result.stdout or result.stderr).strip()
        if "VALID" in out.upper():
            ok(out)
        else:
            fail(out or "Unknown error")
    elif choice == "2":
        result = subprocess.run(
            [sys.executable, "-c",
             "from utils.license_validator import license_status; "
             "import json; print(json.dumps(license_status(), indent=2))"],
            cwd=str(PYTHON_CORE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        out = (result.stdout or result.stderr).strip()
        print(c(f"   {out}", _C.WHITE))
    elif choice == "3":
        result = subprocess.run(
            [sys.executable, "-c",
             "from payment.config import PLANS; "
             "import json; print(json.dumps({k: {'name':v.name,'price':v.price_usd,'days':v.duration_days,'perks':v.perks} for k,v in PLANS.items()}, indent=2))"],
            cwd=str(PYTHON_CORE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        out = (result.stdout or result.stderr).strip()
        print(c(f"   {out}", _C.WHITE))
    elif choice == "4":
        owner_management()
    print()

# ──────────────────────────────────────────────────────────────────────
# Main menu loop
# ──────────────────────────────────────────────────────────────────────
MENU = [
    ("1", "🚀  Phoenix Engine CLI",           "start_cli"),
    ("2", "💰  Payment / License Server",      "start_payment_server"),
    ("3", "🟢  Node WhatsApp Bridge",          "start_node_bridge"),
    ("4", "🌐  Web SOC Dashboard",             "open_web_dashboard"),
    ("5", "📱  Mobile App (Expo)",             "mobile_app_helper"),
    ("6", "📦  Build Share Package",           "build_share_package"),
    ("7", "🔑  License Management",            "license_management"),
    ("8", "🔧  Install Dependencies",          "install_dependencies"),
    ("9", "🩺  System Diagnostics",            "run_diagnostics"),
    ("0", "👋  Exit",                          None),
]

def print_menu():
    banner()
    top = c(f"   ┌{'─' * 44}┐", _C.GOLD)
    mid = c("   │", _C.GOLD)
    bot = c(f"   └{'─' * 44}┘", _C.GOLD)
    print(top)
    print(c(f"   │  🦅  PHOENIX EAGLE — COMMAND CENTER  🦅  │".ljust(52) + "│", _C.GOLD))
    print(bot)
    print()
    for num, label, _ in MENU:
        left = c(f"🦅 [{num}]", _C.GOLD) + " " + c(label[4:], _C.WHITE)
        pad = 42 - len(label[4:]) - 5
        tag = label[:4]
        print(f"   {left}{' ' * max(0, pad)}{c(tag, _C.DIM)}")
    print()
    divider(_C.STEEL)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(c(f"   🕒 {ts}", _C.DIM))
    print()

def main_menu():
    handlers = {fn: name for _, _, name in MENU if name}
    while True:
        print_menu()
        choice = prompt_input("🦅 Enter choice [0-9]").strip()
        handler_name = handlers.get(choice)
        if handler_name:
            print()
            globals()[handler_name]()
            try:
                input(c("   [ PRESS ENTER TO RETURN ]", _C.STEEL))
            except (EOFError, KeyboardInterrupt):
                pass
        elif choice == "0":
            banner("GOODBYE", "Phoenix Eagle awaits your return")
            print(c("   🦅 Thank you for using Phoenix Obliterator Pro 🦅\n", _C.GOLD))
            sys.exit(0)
        else:
            warn("Invalid choice — enter a number 0-9")
            time.sleep(1.2)

# ──────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Ensure backend/python_core is on sys.path so sub-runners can import
    # sibling modules (payment, core, utils, sharing) as packages.
    core_dir = str(PYTHON_CORE)
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)

    # Add backend to path for node_whatsapp imports if needed
    backend_dir = str(ROOT / "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    try:
        main_menu()
    except KeyboardInterrupt:
        clear()
        print(c("\n   🦅 Interrupted — Phoenix Eagle awaits your return 🦅\n", _C.GOLD))
        sys.exit(0)
