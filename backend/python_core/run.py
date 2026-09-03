#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHOENIX EAGLE OBLITERATOR - MASTER LAUNCHER
"""

import os
import sys
import subprocess

# Paths
# run.py and main.py are in the SAME directory (backend/python_core/)
ROOT = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(ROOT, "main.py")

def banner():
    os.system("cls" if os.name == "nt" else "clear")
    print("\033[93m")
    print("  ╔═══════════════════════════════════════════════════╗")
    print("  ║   PHOENIX EAGLE OBLITERATOR - MASTER LAUNCHER     ║")
    print("  ║   🦅 Ultra Pro v3.0 | Cross-Platform              ║")
    print("  ╚═══════════════════════════════════════════════════╝")
    print("\033[0m")

def main():
    banner()

    # Check main.py exists
    if not os.path.exists(MAIN):
        print("\033[91m[✗] main.py not found at:")
        print(f"    {MAIN}\033[0m")
        print("\n[!] Check that the folder structure is correct:")
        print("    backend/python_core/main.py")
        sys.exit(1)

    print("  [1] 🚀 Start Phoenix Engine (CLI)")
    print("  [2] 💰 Start Payment Server + Web Checkout")
    print("  [3] ☁️  Start Cloud API Server (not configured yet)")
    print("  [0] Exit")
    print()
    choice = input("  Enter choice: ").strip()

    if choice == "1":
        print("\n[✓] Launching Phoenix Engine...\n")
        subprocess.run([sys.executable, MAIN])
    elif choice == "2":
        start_payment_server()
    elif choice == "3":
        print("\n[!] This module is part of the NEW prompts (Prompt 2 & 5).")
        print("    Run those prompts first to generate this module.")
        input("\nPress Enter to continue...")
        main()
    elif choice == "0":
        print("\nGoodbye! 🦅")
        sys.exit(0)
    else:
        main()


def start_payment_server():
    """Start the Flask payment / licensing web server."""
    from payment.config import CONFIG
    host = CONFIG.server_host
    port = CONFIG.server_port
    print(f"\n[✓] Launching Payment Server on http://{host}:{port}\n")
    print("    Dashboard: http://{}:{}/checkout/checkout.html".format(host, port))
    print("    Press Ctrl+C to stop.\n")
    try:
        # Import creates the Flask app and serves the checkout page + webhooks.
        from payment.payment_server import create_app
        create_app().run(host=host, port=port, debug=False)
    except KeyboardInterrupt:
        print("\n\nServer stopped. 🦅")
    except Exception as exc:
        print(f"\n[✗] Could not start payment server: {exc}")
    input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Exiting...")
        sys.exit(0)