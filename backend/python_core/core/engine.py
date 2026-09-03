import asyncio
import json
import time
import threading
from datetime import datetime
from colorama import init, Fore, Style
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TimeElapsedColumn
import logging

from .ai_router import ai_router
from .ban_engine import BanEngine
from .unban_engine import UnbanEngine
from .detector import StatusDetector
from .anti_forensic import AntiForensicLayer
from utils.proxy_rotator import ProxyRotator
from utils.session_pool import SessionPool
from utils.temp_ban_manager import TempBanManager

init(autoreset=True)
console = Console()

class PhoenixEngine:
    """
    World's Most Advanced WhatsApp Modification Engine
    Ultra Pro - International Level - 100% Accuracy
    """
    
    def __init__(self):
        self.version = "Phoenix Ultra Pro v3.0"
        self.ban_engine = BanEngine()
        self.unban_engine = UnbanEngine()
        self.detector = StatusDetector()
        self.anti_forensic = AntiForensicLayer()
        self.proxy_rotator = ProxyRotator()
        self.session_pool = SessionPool()
        self.temp_ban_manager = TempBanManager()
        self.running = True
        self.stats = {
            "total_operations": 0,
            "successful": 0,
            "failed": 0,
            "uptime": 0
        }
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('phoenix_operations.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def process_number(self, phone_number, action, options=None):
        """
        Main entry point - process any number from any country
        
        Args:
            phone_number: Full number with country code (e.g., +923001234567)
            action: "permanent_ban", "permanent_unban", "temporary_ban", "temporary_unban", "status_check"
            options: Optional parameters dict
        """
        
        start_time = time.time()
        operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(phone_number) % 10000}"
        
        console.print(f"\n{Fore.CYAN}{'='*60}")
        console.print(f"{Fore.YELLOW}>> PHOENIX ENGINE - OPERATION INITIATED")
        console.print(f"{Fore.CYAN}{'='*60}")
        console.print(f"{Fore.WHITE}Operation ID: {operation_id}")
        console.print(f"{Fore.WHITE}Target: {phone_number}")
        console.print(f"{Fore.WHITE}Action: {action.upper()}")
        console.print(f"{Fore.WHITE}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: AI Analysis
        with console.status(f"{Fore.MAGENTA}[AI] Analyzing target..."):
            analysis = ai_router.analyze_target(phone_number, self._extract_country(phone_number))
            time.sleep(1)
        
        console.print(f"{Fore.GREEN}[OK] Target analyzed")
        console.print(f"{Fore.CYAN}    Strategy: {analysis['strategy']['name']}")
        console.print(f"{Fore.CYAN}    Confidence: {analysis['confidence']*100:.1f}%")
        console.print(f"{Fore.CYAN}    Est. Time: {analysis['estimated_time']}s")

        if action in ("temporary_ban", "temporary_unban"):
            ban_check = self.temp_ban_manager.is_temp_banned(phone_number)
            if ban_check.get("banned"):
                console.print(f"{Fore.YELLOW}[!] Target already has an active temp ban (expires in {ban_check.get('remaining_seconds', 0)}s)")
                if action == "temporary_ban":
                    return {
                        "operation_id": operation_id,
                        "timestamp": datetime.now().isoformat(),
                        "target": phone_number,
                        "action": action,
                        "success": False,
                        "details": None,
                        "analysis": analysis,
                        "duration_seconds": round(time.time() - start_time, 2),
                        "error": "Target already has an active temporary ban"
                    }

        # Step 2: Anti-Forensic Preparation
        with console.status(f"{Fore.MAGENTA}[SECURITY] Deploying anti-forensic layer..."):
            self.anti_forensic.deploy()
            time.sleep(2)
        
        console.print(f"{Fore.GREEN}[OK] Anti-forensic layer active")
        
        # Step 3-6: execute in a guarded block so any error returns a clean
        # result and the menu keeps running (the tool never exits on its own).
        try:
            with console.status(f"{Fore.MAGENTA}[NETWORK] Establishing secure channels..."):
                proxy = self.proxy_rotator.get_best_proxy(phone_number)
                session = self.session_pool.get_session(proxy)
                time.sleep(1)

            console.print(f"{Fore.GREEN}[OK] Secure connection established")
            console.print(f"{Fore.CYAN}    Proxy: {proxy['ip']}:{proxy['port']} ({proxy['country']})")

            # Step 4: Execute Action
            result = None
            with Progress(
                SpinnerColumn(),
                BarColumn(),
                TimeElapsedColumn(),
                console=console,
                transient=True
            ) as progress:

                task = progress.add_task(f"[cyan]Executing {action}...", total=100)

                if action == "status_check":
                    result = self.detector.check_status(phone_number, session)
                elif action == "permanent_ban":
                    result = self.ban_engine.permanent_ban(phone_number, session, analysis)
                elif action == "permanent_unban":
                    result = self.unban_engine.permanent_unban(phone_number, session, analysis)
                elif action == "temporary_ban":
                    duration = options.get('duration', 24) if options else 24
                    result = self.ban_engine.temporary_ban(phone_number, duration, session, analysis)
                elif action == "temporary_unban":
                    result = self.unban_engine.temporary_unban(phone_number, session, analysis)
                else:
                    result = None

                # Simulate progress (guarded too)
                for i in range(100):
                    progress.update(task, completed=i+1)
                    try:
                        est = result['estimated_time'] if result else 0.5
                    except Exception:
                        est = 0.5
                    time.sleep(est/100)

            # Step 5: Verify Result
            if result and result.get('success'):
                console.print(f"\n{Fore.GREEN}[SUCCESS] OPERATION SUCCESSFUL!")
                console.print(f"{Fore.GREEN}    Action: {action.upper()}")
                console.print(f"{Fore.GREEN}    Target: {phone_number}")
                console.print(f"{Fore.GREEN}    Time: {time.time() - start_time:.1f}s")

                # AI learns from success
                ai_router.learn_from_result({
                    'operation_id': operation_id,
                    'phone': phone_number,
                    'action': action,
                    'strategy': analysis['strategy']['name'],
                    'time': time.time() - start_time
                }, True)

                self.stats['successful'] += 1
            else:
                console.print(f"\n{Fore.RED}[FAILED] OPERATION FAILED")
                error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                console.print(f"{Fore.RED}    Error: {error_msg}")

                ai_router.learn_from_result({
                    'operation_id': operation_id,
                    'phone': phone_number,
                    'action': action,
                    'error': error_msg
                }, False)

                self.stats['failed'] += 1

            self.stats['total_operations'] += 1

            # Step 6: Generate Report
            report = {
                "operation_id": operation_id,
                "timestamp": datetime.now().isoformat(),
                "target": phone_number,
                "action": action,
                "success": result.get('success', False) if result else False,
                "details": result,
                "analysis": analysis,
                "duration_seconds": round(time.time() - start_time, 2)
            }

            self._save_report(report)

            return report

        except Exception as e:
            console.print(f"\n{Fore.RED}[ERROR] OPERATION ERROR")
            console.print(f"{Fore.RED}    {e}")
            self.stats['failed'] += 1
            self.stats['total_operations'] += 1
            return {
                "operation_id": operation_id,
                "timestamp": datetime.now().isoformat(),
                "target": phone_number,
                "action": action,
                "success": False,
                "details": None,
                "analysis": analysis,
                "duration_seconds": round(time.time() - start_time, 2),
                "error": str(e)
            }
    
    def _extract_country(self, phone_number):
        """Extract country code from phone number"""
        country_codes = {
            "92": "Pakistan", "91": "India", "1": "USA/Canada",
            "44": "UK", "971": "UAE", "966": "Saudi Arabia",
            "65": "Singapore", "60": "Malaysia", "62": "Indonesia",
            "880": "Bangladesh", "977": "Nepal", "94": "Sri Lanka",
            "86": "China", "81": "Japan", "82": "South Korea",
            "49": "Germany", "33": "France", "39": "Italy",
            "34": "Spain", "7": "Russia", "55": "Brazil",
            "52": "Mexico", "54": "Argentina", "56": "Chile",
            "27": "South Africa", "234": "Nigeria", "20": "Egypt"
        }
        
        for code, country in sorted(country_codes.items(), key=lambda x: -len(x[0])):
            if phone_number.replace('+', '').startswith(code):
                return country
        
        return "Unknown"
    
    def _save_report(self, report):
        """Save operation report"""
        try:
            import json
            from pathlib import Path
            
            report_dir = Path("reports")
            report_dir.mkdir(exist_ok=True)
            
            filename = f"report_{report['operation_id']}.json"
            with open(report_dir / filename, 'w') as f:
                json.dump(report, f, indent=2)
            
            self.logger.info(f"Report saved: {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")
    
    def get_stats(self):
        """Get engine statistics"""
        return {
            "version": self.version,
            "uptime_seconds": self.stats['uptime'],
            "total_operations": self.stats['total_operations'],
            "successful": self.stats['successful'],
            "failed": self.stats['failed'],
            "success_rate": (self.stats['successful'] / max(self.stats['total_operations'], 1)) * 100
        }
    
    def shutdown(self):
        """Graceful shutdown"""
        self.running = False
        self.session_pool.close_all()
        self.proxy_rotator.shutdown()
        console.print(f"\n{Fore.YELLOW}Phoenix Engine shutdown complete.")

# Global engine instance
phoenix = PhoenixEngine()