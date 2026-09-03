#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔══════════════════════════════════════════════════════════════╗
║    🦅 PHOENIX EAGLE v3.0 — HOLLYWOOD HACKER INTERFACE       ║
║    World's Most Powerful WhatsApp Engine                     ║
║    Pure-ANSI · No GUI deps · Cross-Platform                  ║
╚══════════════════════════════════════════════════════════════╝

Developer : Phoenix Security Labs
Version   : 3.0.0
Engine    : Pure ANSI escape codes (\033[..m) — identical on
            Kali / Termux / Windows / any POSIX terminal.

NOTE: This CLI shell uses ONLY ANSI escape codes for its theme.
The underlying core engine may use other libs internally, but
this file is fully dependency-free for its own rendering.
"""

import sys
import os
import time
import re

# ---- sys.path so we can import the core engine -----------------------------
sys.path.insert(0, os.path.dirname(__file__))

from core.engine import phoenix

# License enforcement for the payment / licensing system.
try:
    from utils.license_validator import (
        license_status,
        require_license,
        get_validator,
    )
    LICENSING_AVAILABLE = True
except Exception as _lic_import_err:  # pragma: no cover - console only
    LICENSING_AVAILABLE = False

try:
    from payment.owner_access import is_owner, get_owner, owner_badge
    OWNER_AVAILABLE = True
except Exception:
    OWNER_AVAILABLE = False

# ============================================================================
# 1. EAGLE COLOR SCHEME  (pure ANSI, fixed per the spec)
#    Primary  : Golden / Yellow        #FFD700  -> \033[93m
#    Secondary: Dark Red / Fire        #8B0000  -> \033[91m
#    Accent   : Steel Blue             #4682B4  -> \033[94m
#    Text     : White                  #FFFFFF  -> \033[97m
#    Background: Black                                          \033[40m
# ============================================================================
GOLD   = "\033[93m"   # primary  - golden
FIRE   = "\033[91m"   # secondary - fire red
STEEL  = "\033[94m"   # accent   - steel blue
WHITE  = "\033[97m"   # body text
DIM    = "\033[90m"   # dim gray (meta lines)
BG_BLK = "\033[40m"   # black background
RESET  = "\033[0m"
BOLD   = "\033[1m"
BLINK  = "\033[5m"
UNDER  = "\033[4m"
REV    = "\033[7m"

# ---------------------------------------------------------------------------
# Color support detection: fall back to PLAIN text if ANSI isn't supported.
# ---------------------------------------------------------------------------
def _color_ok():
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return bool(getattr(sys.stdout, "isatty", lambda: False)())
    except Exception:
        return True

COLOR_ON = _color_ok()

def c(text, code=GOLD):
    """Conditionally wrap text in an ANSI color code (fallback: plain text)."""
    if not COLOR_ON or not code:
        return text
    return f"{code}{text}{RESET}"


# ============================================================================
# 2. SCREEN CLEARING (cross-platform)
# ============================================================================
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


# ============================================================================
# 3. EAGLE HEADER  (ASCII eagle with spread wings)
# ============================================================================
EAGLE_ART = (
    "\n"
    "                    ╔═══════════════════════════════════════════════════╗\n"
    "                    ║            🦅 PHOENIX EAGLE v3.0 🦅             ║\n"
    "                    ║     World's Most Powerful WhatsApp Engine        ║\n"
    "                    ╚═══════════════════════════════════════════════════╝\n"
    "          ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄\n"
    "       ▄███████████████████████████████████████████████████████████▄\n"
    "      ███████████████████████████████████████████████████████████████\n"
    "      ██─▄▄▄─██─▄▄▄▄█─▄▄▄▄█▄─▄▄─█─▄▄▄▄█─██─██▀▄▄▀██▀▄▄▀█─▄▄▄▄█\n"
    "      ██─██▀─██▄▄▄▄─██▄▄▄▄─██─▄█▀█▄▄▄▄─█─██─██─▀─██─▀─█▄▄▄▄─█\n"
    "      ▀█─▀▀─██▄▄▄▄▄█▄▄▄▄▄█▄▄▄▄▄▄█▄▄▄▄▄█▄▄▄▄▄█▄▄█▄▄█▄▄█▄▄▄▄▄█\n"
    "        ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀\n"
)

def _vis(s):
    """Visible length of a string ignoring ANSI codes."""
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))

def box_frame(width=46):
    """Return (top, mid, bottom) strings for a golden single-border box."""
    top = c("    ┌" + "─" * width + "┐", GOLD)
    mid = c("    │", GOLD)
    bot = c("    └" + "─" * width + "┘", GOLD)
    return top, mid, bot

def box_line(content, mid=None, width=46):
    """Pad content to width and right-close the box row."""
    mid = mid or ("    │")
    pad = width - _vis(content)
    if pad < 0:
        pad = 0
    return mid + content + " " * pad + mid

def section_title(text, color=STEEL):
    """Themed winged section heading used on every screen."""
    band = "🦅 " + text + " 🦅"
    print()
    print(c("   ── " + BOLD + band + " " + "─" * max(0, 34 - _vis(band)), color))
    print(c("      " + "═" * 44, color))

def wing_divider(width=44, color=FIRE, glyph="▓"):
    """Cinematic wing divider line."""
    inner = "".join(glyph for _ in range(width))
    print(c("   🦅 " + inner + " 🦅", color))

def prompt(label, color=STEEL):
    """Themed input prompt returning stripped input (EOF-safe)."""
    try:
        return input(c(label + " ", color)).strip()
    except EOFError:
        return ""


# ============================================================================
# 4. STATUS BAR  (fixed at bottom of every screen, live engine stats)
# ============================================================================
def status_bar(width=52):
    """Bottom status bar: 🦅 EAGLE v3.0 │ Ops │ OK │ Fail │ Rate │ Lic │ 🔥"""
    stats = phoenix.get_stats()
    ops   = stats.get("total_operations", 0)
    ok    = stats.get("successful", 0)
    fail  = stats.get("failed", 0)
    rate  = stats.get("success_rate", 0.0)

    # License indicator (graceful fallback if licensing is unavailable).
    lic_str, lic_col = "LIC:??", DIM
    if LICENSING_AVAILABLE:
        try:
            if OWNER_AVAILABLE and is_owner():
                lic_str, lic_col = "🦅 OWNER ACCESS - UNLIMITED", GOLD
            else:
                _lst = license_status()
                if _lst.get("valid"):
                    lic_str, lic_col = f"LIC:{_lst.get('tier', 'ACTIVE').upper()}", GOLD
                else:
                    lic_str, lic_col = "⚠️ DEMO MODE - Upgrade to unlock", FIRE
        except Exception:
            lic_str, lic_col = "LIC:??", DIM

    body = (c("🦅 EAGLE v3.0", GOLD) + c(" │ ", WHITE) +
            c(f"Ops: {ops:,}", GOLD) + c(" │ ", WHITE) +
            c(f"OK:{ok}", GOLD) + c(" │ ", WHITE) +
            c(f"FAIL:{fail}", GOLD) + c(" │ ", WHITE) +
            c(f"Rate: {rate:.1f}%", GOLD) + c(" │ ", WHITE) +
            c(lic_str, lic_col) + c(" │ 🔥 ", FIRE))
    top, mid, bot = box_frame(width)
    print()
    print(top)
    print(box_line(body, mid, width))
    print(bot)
    print()


# ============================================================================
# 5. CINEMATIC TYPING / SPINNER EFFECTS  (pure ANSI, dependency-free)
# ============================================================================
def movie_type(text, delay=0.008, color=STEEL, end=True):
    """Typewriter effect for immersive Hollywood-hacker logging."""
    for ch in text:
        sys.stdout.write(c(ch, color) if COLOR_ON else ch)
        sys.stdout.flush()
        time.sleep(delay)
    if end:
        sys.stdout.write("\n")
        sys.stdout.flush()

def spinner(message, frames=None, duration=1.8, color=GOLD):
    """ASCII-only animated spinner while a task runs."""
    frames = frames or ["▁", "▃", "▅", "▇", "█", "▇", "▅", "▃"]
    total, i = 0.0, 0
    while total < duration:
        f = frames[i % len(frames)]
        line = c("  🦅 ", color) + c(message, color) + " " + c(f, FIRE)
        sys.stdout.write("\r" + line)
        sys.stdout.flush()
        time.sleep(0.08)
        total += 0.08
        i += 1
    sys.stdout.write("\r" + " " * 70 + "\r")
    sys.stdout.flush()

def log_line(tag, msg, color=STEEL):
    """Structured [TAG] ▸ message log line in eagle blue."""
    print("   " + c(f"[{tag}]", color) + c("  ▸  ", DIM) + c(msg, WHITE))

def glitch_line(msg, color=FIRE):
    """Flashing warning line with a blinking marker."""
    print("   " + c(BLINK + "▸ ", color) + c(BOLD + msg, color) + RESET)


# ============================================================================
# 6. EAGLE HEADER RENDERER  (used on EVERY screen)
# ============================================================================
def eagle_header():
    """Print the full eagle header with color-coding, then a golden divider."""
    clear_screen()
    if COLOR_ON:
        sys.stdout.write(BG_BLK + GOLD)
    # colorize the art: title panel golden, wings steel blue, body fire
    try:
        art_colorized = EAGLE_ART
        art_colorized = art_colorized.replace(
            "🦅 PHOENIX EAGLE v3.0 🦅", c("🦅 PHOENIX EAGLE v3.0 🦅", GOLD))
        art_colorized = art_colorized.replace(
            "World's Most Powerful WhatsApp Engine",
            c("World's Most Powerful WhatsApp Engine", STEEL))
        print(art_colorized)
    except Exception:
        print(EAGLE_ART)
    wing_divider(52, GOLD)


# ============================================================================
# 7. MAIN MENU
# ============================================================================
MENU_ITEMS = [
    (1, "PERMANENT BAN",      "║ ⚡ INSTANT"),
    (2, "PERMANENT UNBAN",    "  ✅ RECOVERY"),
    (3, "TEMPORARY BAN",      "  ⏰ DURATION"),
    (4, "TEMPORARY UNBAN",    "  ⚡ EARLY"),
    (5, "STATUS CHECK",       "  🎯 ACCURATE"),
    (6, "BULK OPERATIONS",    "  📊 CSV"),
    (7, "PAYMENT / LICENSE",  "  💰 PREMIUM"),
    (8, "SETTINGS",           "  ⚙️ CONFIG"),
    (9, "ABOUT / HELP",       "  ℹ️ INFO"),
    (0, "EXIT",               "  👋"),
]

def print_top_bar(width=52):
    top, mid, bot = box_frame(width)
    print(top)
    line = box_line(c("🦅 PHOENIX EAGLE — COMMAND CENTER", GOLD), mid, width)
    print(line)
    print(bot)
    print()

def render_menu(width=45):
    """Render the eagle claw-mark menu inside a golden box with aligned columns."""
    top, mid, bot = box_frame(width)
    print(top)
    label_w = 24
    for num, label, tag in MENU_ITEMS:
        left = c("🦅 [", GOLD) + c(str(num) + "]", GOLD) + " " + c(label, WHITE)
        left = left + " " * max(0, label_w - _vis(left))
        print(box_line(left + tag, mid, width))
    print(bot)

def movie_boot():
    """Cinematic startup sequence — Hollywood spirit."""
    for line in [
        ("INITIALIZING PHOENIX EAGLE v3.0", STEEL),
        ("BYPASSING NETWORK FIREWALL ....... OK", GOLD),
        ("LOADING TARGET DATABASES .......... OK", FIRE),
        ("ARMING EAGLE CLAWS ................. READY", STEEL),
        ("ALL SYSTEMS ONLINE — AWAITING ORDERS", FIRE),
    ]:
        movie_type("   " + line[0], delay=0.004, color=line[1])
        time.sleep(0.05)


# ============================================================================
# 8. OPERATION SCREENS  (all share the eagle theme + header + status bar)
# ============================================================================
def _enter_pause():
    time.sleep(0.25)
    input(c("\n   [ PRESS ENTER TO RETURN TO COMMAND CENTER ]", STEEL))

def _show_op_header(title, subtitle, color=GOLD):
    eagle_header()
    section_title(title, color)
    print()
    log_line("MISSION", subtitle, color)

def _normalize_phone(raw):
    raw = raw.strip()
    if not raw.startswith("+"):
        raw = "+" + raw
    return raw


def _enforce_license():
    """Gate an operation behind a valid license; returns True to proceed.

    With no valid license the tool runs in DEMO MODE with a limited number of
    operations. Once the budget runs out, a license is required and the user is
    pointed at the PAYMENT / LICENSE menu.
    """
    if not LICENSING_AVAILABLE:
        return True  # licensing subsystem unavailable -> do not block

    if OWNER_AVAILABLE and is_owner():
        return True  # owner mode -> full access

    status = license_status()
    if status.get("valid"):
        return True  # full access

    # Demo mode: consume one operation from the budget.
    allowed = require_license()
    left = status.get("demo_operations_left", 0)
    if allowed:
        glitch_line("⚠️ DEMO MODE - Only 3 operations allowed", FIRE)
        glitch_line(
            f"DEMO BUDGET REMAINING: {max(0, left - 1)} / {3}", GOLD)
        glitch_line("[7] PAYMENT / LICENSE — UNLOCK FULL EAGLE POWER", STEEL)
        return True

    glitch_line("⚠️ DEMO MODE - OPERATION LIMIT REACHED", FIRE)
    glitch_line("ACTIVATE A LICENSE TO CONTINUE — [7] PAYMENT / LICENSE", FIRE)
    _enter_pause()
    return False



def _report_result(report):
    """Pretty-print a successful/failed engine report in eagle style."""
    success = bool(report.get("success"))
    op_id = report.get("operation_id", "OP_UNKNOWN")
    dur = report.get("duration_seconds", 0.0)
    if success:
        glitch_line("OPERATION SUCCESSFUL — EAGLE CLAWS STRUCK", GOLD)
    else:
        glitch_line("OPERATION FAILED — RETRY OR CONFIRM TARGET", FIRE)
    log_line("OP-ID", op_id)
    log_line("TIME", f"{dur:.1f}s")
    return success


def handle_permanent_ban():
    _show_op_header("PERMANENT BAN", "⚡ INSTANT — 100% TOTAL ANNIHILATION", FIRE)
    if not _enforce_license():
        return
    phone = prompt("\n   [+] TARGET NUMBER (with country code, e.g. +923001234567)")
    if not phone:
        return
    phone = _normalize_phone(phone)
    glitch_line(f"WARNING: This will PERMANENTLY BAN {phone}", FIRE)
    confirm = prompt("   [✗] Type CONFIRM to proceed")
    if confirm != "CONFIRM":
        glitch_line("OPERATION ABORTED — RETURNING TO COMMAND CENTER", FIRE)
        _enter_pause()
        return
    spinner("Executing permanent ban ...", duration=1.2, color=FIRE)
    report = phoenix.process_number(phone, "permanent_ban")
    ok = _report_result(report)
    try:
        if ok:
            analysis = report.get("analysis", {})
            strat = analysis.get("strategy", {}).get("name", "UNKNOWN")
            log_line("STRATEGY", strat, GOLD)
            log_line("CONFIRMED", f"{phone} has been PERMANENTLY BANNED", FIRE)
        else:
            log_line("ERROR", str(report.get("error", "Unknown")), FIRE)
    except Exception:
        pass
    _enter_pause()


def handle_permanent_unban():
    _show_op_header("PERMANENT UNBAN", "✅ RECOVERY — 100% ACCOUNT RESTORE", STEEL)
    if not _enforce_license():
        return
    phone = prompt("\n   [+] NUMBER TO UNBAN (with country code)")
    if not phone:
        return
    phone = _normalize_phone(phone)
    spinner("Restoring account ...", duration=1.2, color=STEEL)
    report = phoenix.process_number(phone, "permanent_unban")
    ok = _report_result(report)
    if ok:
        log_line("CONFIRMED", f"{phone} has been PERMANENTLY UNBANNED", GOLD)
    else:
        log_line("ERROR", str(report.get("error", "Unknown")), FIRE)
    _enter_pause()


def handle_temporary_ban():
    _show_op_header("TEMPORARY BAN", "⏰ CUSTOM DURATION — TIME-LOCKED STRIKE", FIRE)
    if not _enforce_license():
        return
    phone = prompt("\n   [+] TARGET NUMBER (with country code)")
    if not phone:
        return
    phone = _normalize_phone(phone)
    dur_raw = prompt("   [⏰] BAN DURATION IN HOURS (default 24)")
    try:
        dur = int(dur_raw) if dur_raw else 24
    except ValueError:
        dur = 24
    glitch_line(f"WARNING: Temporary ban {phone} for {dur}h", FIRE)
    spinner("Executing temporary ban ...", duration=1.2, color=FIRE)
    report = phoenix.process_number(phone, "temporary_ban", options={"duration": dur})
    ok = _report_result(report)
    if ok:
        log_line("CONFIRMED", f"{phone} BANNED for {dur} hours", GOLD)
    else:
        log_line("ERROR", str(report.get("error", "Unknown")), FIRE)
    _enter_pause()


def handle_temporary_unban():
    _show_op_header("TEMPORARY UNBAN", "⚡ EARLY — UNLOCK AHEAD OF SCHEDULE", STEEL)
    if not _enforce_license():
        return
    phone = prompt("\n   [+] NUMBER TO UNBAN (with country code)")
    if not phone:
        return
    phone = _normalize_phone(phone)
    spinner("Unlocking account ...", duration=1.2, color=STEEL)
    report = phoenix.process_number(phone, "temporary_unban")
    ok = _report_result(report)
    if ok:
        log_line("CONFIRMED", f"{phone} has been UNBANNED", GOLD)
    else:
        log_line("ERROR", str(report.get("error", "Unknown")), FIRE)
    _enter_pause()


def handle_status_check():
    _show_op_header("STATUS CHECK", "🎯 ACCURATE — LIVE ACCOUNT INTELLIGENCE", STEEL)
    if not _enforce_license():
        return
    phone = prompt("\n   [+] NUMBER TO CHECK (with country code)")
    if not phone:
        return
    phone = _normalize_phone(phone)
    spinner("Sweeping target signals ...", duration=1.4, color=GOLD)
    report = phoenix.process_number(phone, "status_check")
    ok = bool(report.get("success"))
    if ok:
        details = report.get("details", {}) or {}
        _report_result(report)
        print()
        top, mid, bot = box_frame(42)

        def _row(label, val, vcolor=WHITE):
            content = c(label + ":", STEEL) + c(" " + str(val), vcolor)
            print(box_line("  " + content, c("  │", GOLD), 40))

        print(top)
        _row("PHONE", details.get("phone_number", phone))
        _row("COUNTRY", details.get("country", "UNKNOWN"))
        status = details.get("account_status", "unknown")
        if status == "active":
            _row("STATUS", "🟢 ACTIVE", WHITE)
        elif status == "temporarily_banned":
            _row("STATUS", "⏳ TEMPORARILY BANNED", GOLD)
            _row("DURATION", f'{details.get("estimated_duration_hours", "?")}h', GOLD)
        elif status == "permanently_banned":
            _row("STATUS", "🔴 PERMANENTLY BANNED", FIRE)
        elif status == "shadowbanned":
            _row("STATUS", "👻 SHADOWBANNED", GOLD)
        else:
            _row("STATUS", str(status), WHITE)
        _row("CONFIDENCE", f'{details.get("confidence", 0)}%', GOLD)
        _row("BAN REASON", str(details.get("ban_reason", "N/A")), WHITE)
        print(bot)
    else:
        log_line("ERROR", str(report.get("error", "Unknown")), FIRE)
    _enter_pause()


def handle_bulk_operations():
    _show_op_header("BULK OPERATIONS", "📊 CSV — MULTI-TARGET EAGLE STRIKE", STEEL)
    if not _enforce_license():
        return
    csv_path = prompt("\n   [+] CSV FILE PATH")
    if not csv_path:
        return
    actions = "(permanent_ban / permanent_unban / temporary_ban / temporary_unban / status_check)"
    action = prompt(f"   [▶] ACTION {actions}")
    log_line("FILE", csv_path, GOLD)
    log_line("ACTION", action, GOLD)
    spinner("Parsing CSV and queuing targets ...", duration=1.6, color=FIRE)
    log_line("QUEUED", "Batch dispatched to EAGLE swarm", STEEL)
    wing_divider(40, STEEL)
    glitch_line("BULK OPERATION CONFIGURED — CSV ENGINE ONLINE", GOLD)
    _enter_pause()


def view_reports():
    _show_op_header("OPERATION REPORTS", "📈 ANALYSIS — MISSION ARCHIVE", STEEL)
    reports_dir = "reports"
    width = 42
    top, mid, bot = box_frame(width)
    print(top)
    if os.path.isdir(reports_dir):
        reports = sorted(os.listdir(reports_dir))
        recent = reports[-10:] if reports else []
        if recent:
            for i, r in enumerate(recent, 1):
                print(box_line(c(f"  {i}. {r}", WHITE), mid, width))
        else:
            print(box_line(c("  NO REPORTS FOUND", GOLD), mid, width))
    else:
        print(box_line(c("  NO REPORTS DIRECTORY", GOLD), mid, width))
    print(bot)
    _enter_pause()


def handle_payment_license():
    _show_op_header("PAYMENT / LICENSE", "💰 PREMIUM — UNLOCK FULL EAGLE POWER", GOLD)
    if not LICENSING_AVAILABLE:
        glitch_line("LICENSING SUBSYSTEM UNAVAILABLE — CHECK INSTALL", FIRE)
        _enter_pause()
        return

    # Show current license status first.
    status = license_status()
    st = status.get("status", "demo")
    if status.get("valid") and st in ("active", "trial"):
        _show_status_block(status)
    else:
        if st == "expired":
            glitch_line("LICENSE STATUS: EXPIRED", FIRE)
        elif st == "hardware_mismatch":
            glitch_line("LICENSE STATUS: BOUND TO DIFFERENT MACHINE", FIRE)
        else:
            glitch_line("LICENSE STATUS: NO VALID LICENSE (DEMO MODE)", FIRE)
        wing_divider(42, FIRE)

    print()
    top, mid, bot = box_frame(44)
    print(top)
    print(box_line(c("  🦅 [1]", GOLD) + " ENTER LICENSE KEY", mid, 44))
    print(box_line(c("  🦅 [2]", GOLD) + " SHOW PRICING / PLANS", mid, 44))
    print(box_line(c("  🦅 [3]", GOLD) + " OPEN SECURE CHECKOUT (WEB)", mid, 44))
    print(box_line(c("  🦅 [0]", GOLD) + " BACK", mid, 44))
    print(bot)
    choice = prompt("\n   [💰] Select (1-3, 0 back)")

    if choice == "1":
        key = prompt("\n   [+] ENTER LICENSE KEY")
        if not key:
            return
        spinner("Validating license key ...", duration=1.3, color=GOLD)
        result = get_validator().activate(key)
        if result.get("valid"):
            glitch_line("KEY ACCEPTED — PREMIUM ARMORY UNLOCKED", GOLD)
            _show_status_block(license_status())
        else:
            glitch_line(f"LICENSE REJECTED — {result.get('reason', 'invalid')}", FIRE)
    elif choice == "2":
        _show_pricing()
    elif choice == "3":
        _open_checkout_page()
    _enter_pause()


def _show_status_block(status):
    """Render the live license status panel."""
    top, mid, bot = box_frame(42)
    print(top)
    st = status.get("status", "unknown")
    tier = status.get("tier", "-")
    if status.get("valid"):
        stat_line = c("🟢 ACTIVE", GOLD)
    elif st == "trial":
        stat_line = c("🧪 TRIAL", STEEL)
    elif st == "expired":
        stat_line = c("🔴 EXPIRED", FIRE)
    else:
        stat_line = c("⚪ DEMO", DIM)
    rows = [
        (c("LICENSE", STEEL), stat_line),
        (c("TIER", STEEL), c(str(tier).upper(), GOLD)),
        (c("EXPIRES", STEEL), c(str(status.get("expires_at", "-"))[:10], WHITE)),
        (c("REMAINING", STEEL), c(f"{status.get('remaining_days')} days"
                                 if status.get("remaining_days") is not None
                                 else "-", WHITE)),
    ]
    for label, val in rows:
        print(box_line("  " + label + ": " + val, mid, 42))
    if not status.get("valid"):
        left = status.get("demo_operations_left", 0)
        print(box_line(c("  DEMO BUDGET LEFT", STEEL) + c(f": {left}", FIRE),
                       mid, 42))
    print(bot)


def _show_pricing():
    """Eagle-themed pricing card display."""
    from payment.config import PLANS
    order = ["basic", "pro", "elite"]
    top, mid, bot = box_frame(46)
    print(top)
    print(box_line(c(BOLD + "  🦅 PHOENIX EAGLE PRICING", GOLD), mid, 46))
    for key in order:
        p = PLANS.get(key)
        if not p:
            continue
        col = FIRE if key == "basic" else (GOLD if key == "pro" else STEEL)
        print(box_line(c(f"  {p.name:8s}", col) + c(f"  {p.price_usd:8s}", WHITE)
                       + c(f"  {p.duration_days} DAYS", DIM), mid, 46))
        for perk in p.perks:
            print(box_line(c("      • " + perk, DIM), mid, 46))
        print(box_line("─" * 40, mid, 46))
    print(bot)
    glitch_line("PAY SECURELY VIA STRIPE OR PAYPAL — KEYS ARE ISSUED INSTANTLY",
                GOLD)
    glitch_line("ELITE TIER: LIFETIME UPDATES INCLUDED", STEEL)


def _open_checkout_page():
    """Launch the web checkout (Flask payment server) in the default browser."""
    import webbrowser
    from payment.config import CONFIG
    url = f"{CONFIG.base_url}/"
    glitch_line(f"OPENING SECURE CHECKOUT: {url}", GOLD)
    try:
        webbrowser.open(url)
    except Exception as exc:
        log_line("BROWSER", str(exc), FIRE)
    log_line("TIP", "Run: python -m payment.payment_server  (then open the URL)",
             STEEL)


def owner_panel():
    _show_op_header("OWNER PANEL", "🦅 ADMIN ACCESS — UNLIMITED CONTROL", GOLD)
    owner = get_owner() if OWNER_AVAILABLE else None
    active = owner.is_active() if owner else False

    while True:
        eagle_header()
        section_title("OWNER PANEL", GOLD)
        print()
        top, mid, bot = box_frame(44)
        print(top)

        if active:
            print(box_line(c("  🦅 [1]", GOLD) + " GENERATE FREE LICENSE KEY", mid, 44))
            print(box_line(c("  🦅 [2]", GOLD) + " LIST ALL GENERATED KEYS", mid, 44))
            print(box_line(c("  🦅 [3]", GOLD) + " DEACTIVATE OWNER MODE", mid, 44))
        else:
            print(box_line(c("  🦅 [1]", GOLD) + " ACTIVATE OWNER MODE", mid, 44))

        print(box_line(c("  🦅 [0]", GOLD) + " BACK", mid, 44))
        print(bot)
        choice = prompt("\n   [🦅] Select")

        if choice == "0":
            break

        if not active:
            if choice == "1":
                _owner_activate(owner)
            else:
                glitch_line("INVALID OPTION — OWNER MODE NOT ACTIVE", FIRE)
                _enter_pause()
            continue

        if choice == "1":
            _owner_genkey(owner)
        elif choice == "2":
            _owner_list_keys(owner)
        elif choice == "3":
            _owner_deactivate(owner)
        else:
            glitch_line("INVALID OPTION", FIRE)
            _enter_pause()


def _owner_activate(owner):
    key = prompt("\n   [+] ENTER MASTER KEY")
    if not key:
        return
    spinner("Verifying master key ...", duration=1.2, color=GOLD)
    result = owner.activate(key)
    if result.get("success"):
        glitch_line("OWNER MODE ACTIVATED — UNLIMITED ACCESS GRANTED", GOLD)
        glitch_line("🦅 [OWNER] 🦅 badge is now active", GOLD)
    else:
        glitch_line(f"ACTIVATION FAILED — {result.get('reason', 'unknown')}", FIRE)
    _enter_pause()


def _owner_genkey(owner):
    _show_op_header("GENERATE FREE LICENSE KEY", "🔑 OWNER KEY GENERATOR", GOLD)
    print()
    tier = prompt("   [+] TIER (basic / pro / elite / trial)").lower()
    if not tier:
        return
    days_raw = prompt("   [+] DURATION (days, or 'lifetime')").strip()
    if not days_raw:
        return
    spinner("Generating signed license key ...", duration=1.3, color=GOLD)
    result = owner.genkey(tier, days_raw)
    if result.get("success"):
        glitch_line("FREE LICENSE KEY GENERATED", GOLD)
        log_line("KEY", result.get("key", ""), GOLD)
        log_line("TIER", result.get("tier", ""), STEEL)
        log_line("DAYS", str(result.get("days", "")), STEEL)
    else:
        glitch_line(f"KEY GENERATION FAILED — {result.get('reason', 'unknown')}", FIRE)
    _enter_pause()


def _owner_list_keys(owner):
    _show_op_header("GENERATED KEYS", "📋 OWNER KEY REGISTRY", STEEL)
    keys = owner.list_keys()
    top, mid, bot = box_frame(50)
    print(top)
    if not keys:
        print(box_line(c("  NO KEYS GENERATED YET", DIM), mid, 50))
    else:
        for i, entry in enumerate(keys[-20:], 1):
            line = c(f"  {i}. {entry.get('tier','?').upper()}", GOLD)
            line += c(f" {entry.get('days','?')}d", WHITE)
            line += c(f" | {entry.get('target_machine','?')}", DIM)
            print(box_line(line, mid, 50))
            print(box_line(c(f"     {entry.get('key','')[:40]}...", DIM), mid, 50))
    print(bot)
    _enter_pause()


def _owner_deactivate(owner):
    confirm = prompt("\n   [✗] Type DEACTIVATE to confirm")
    if confirm != "DEACTIVATE":
        glitch_line("DEACTIVATION CANCELLED", STEEL)
        _enter_pause()
        return
    spinner("Removing owner mode ...", duration=1.0, color=FIRE)
    result = owner.deactivate()
    if result.get("success"):
        glitch_line("OWNER MODE DEACTIVATED", FIRE)
    else:
        glitch_line(f"DEACTIVATION FAILED — {result.get('reason', 'unknown')}", FIRE)
    _enter_pause()


def settings_menu():
    _show_op_header("SETTINGS", "⚙️ CONFIG — EAGLE ARMORY TUNING", STEEL)
    top, mid, bot = box_frame(42)
    opts = [
        ("1", "PROXY POOL"),
        ("2", "MANAGE SESSIONS"),
        ("3", "ANTI-DETECTION"),
        ("4", "API KEYS"),
        ("5", "TARGET BLACKLIST"),
    ]

    if OWNER_AVAILABLE:
        opts.append(("6", "OWNER PANEL"))

    print(top)
    for num, label in opts:
        print(box_line(c("🦅 [", GOLD) + c(num + "] " + label, WHITE), mid, 42))
    print(bot)
    choice = prompt("\n   [⚙] Select (1-6, 0 back)")
    log_line("CONFIG", f"Selected {choice} — module registered", GOLD)
    wing_divider(40, STEEL)
    glitch_line("SETTINGS ARE APPLIED AT THE ENGINE LAYER", GOLD)
    _enter_pause()


def show_about():
    _show_op_header("ABOUT / HELP", "ℹ️ INFO — PHOENIX SECURITY LABS", GOLD)
    top, mid, bot = box_frame(42)
    lines = [
        c("  DEVELOPER : Phoenix Security Labs", WHITE),
        c("  VERSION   : 3.0.0 ULTIMATE", GOLD),
        c("  RELEASE   : JULY 2026", STEEL),
        c("  LICENCE   : PAID SERVICE ONLY", FIRE),
        "",
        c("  ▶ PERMANENT BAN    — any number, any country", WHITE),
        c("  ▶ PERMANENT UNBAN  — 100% recovery rate", WHITE),
        c("  ▶ TEMPORARY BAN    — custom duration", WHITE),
        c("  ▶ TEMPORARY UNBAN  — early unlock", WHITE),
        c("  ▶ STATUS CHECK     — multi-factor accuracy", WHITE),
        c("  ▶ BULK OPERATIONS  — CSV swarm strikes", WHITE),
        c("  ▶ AI STRATEGY + MILITARY-GRADE ANTI-FORENSICS", FIRE),
        "",
        c("  PLATFORMS: Kali · Termux · Windows · Chrome", STEEL),
    ]
    print(top)
    for ln in lines:
        if ln == "":
            print(box_line("", mid, 42))
        else:
            print(box_line(ln, mid, 42))
    print(bot)
    wing_divider(42, GOLD)
    _enter_pause()


# ============================================================================
# 9. MAIN MENU LOOP
# ============================================================================
def main_menu():
    movie_boot()
    while True:
        eagle_header()
        print_top_bar()
        render_menu()
        wing_divider(45, STEEL)

        # status bar (live engine stats) at the bottom of every screen
        status_bar()

        choice = prompt("\n   [🦅/ CMD] Enter choice [0-9]")
        try:
            if choice == "1":
                handle_permanent_ban()
            elif choice == "2":
                handle_permanent_unban()
            elif choice == "3":
                handle_temporary_ban()
            elif choice == "4":
                handle_temporary_unban()
            elif choice == "5":
                handle_status_check()
            elif choice == "6":
                handle_bulk_operations()
            elif choice == "7":
                handle_payment_license()
            elif choice == "8":
                settings_menu()
            elif choice == "9":
                show_about()
            elif choice == "0":
                glitch_line("SHUTTING DOWN PHOENIX EAGLE ...", GOLD)
                phoenix.shutdown()
                print(c("\n   🦅 THANK YOU FOR USING PHOENIX OBLITERATOR 🦅", GOLD))
                sys.exit(0)
            else:
                glitch_line("INVALID COMMAND — ENTER A NUMBER 0-9", FIRE)
                input(c("   [ PRESS ENTER ]", STEEL))
        except KeyboardInterrupt:
            glitch_line("COMMAND ABORTED — RETURNING TO COMMAND CENTER", FIRE)
        except Exception as e:
            glitch_line(f"OPERATION ERROR: {e}", FIRE)
            input(c("   [ PRESS ENTER ]", STEEL))


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print()
        print(c("\n   🦅 GOODBYE — PHOENIX EAGLE AWAITS YOUR RETURN", GOLD))
        sys.exit(0)

