import random
import time
import json

from utils.temp_ban_manager import TempBanManager

class UnbanEngine:
    """
    Advanced Unban Engine - Multiple recovery methodologies
    """
    
    def __init__(self):
        self.methods = [
            self._appeal_unban,
            self._recovery_unban,
            self._token_reset_unban,
            self._clone_merge_unban,
            self._api_bypass_unban
        ]
        self.temp_ban_manager = TempBanManager()
    
    def permanent_unban(self, phone_number, session, analysis):
        """Unban permanently banned number"""
        
        print(f"[UNBAN] Attempting permanent unban for {phone_number}")
        print(f"[UNBAN] 5 methods available, trying each...")
        
        results = []
        for method in self.methods:
            try:
                result = method(phone_number, session, "permanent")
                results.append(result)
                
                if result.get('success'):
                    print(f"[OK] Method succeeded: {result['method_name']}")
                    
                    # Verify unban
                    verification = self._verify_unban(phone_number, session)
                    if verification['active']:
                        return {
                            'success': True,
                            'method_used': result['method_name'],
                            'methods_attempted': len(results),
                            'verification': verification,
                            'estimated_time': 180,
                            'details': result
                        }
                
                time.sleep(random.uniform(0.01, 0.05))
                
            except Exception as e:
                print(f"[!] Method failed: {e}")
                continue
        
        return {
            'success': False,
            'error': 'All unban methods exhausted — target could not be recovered',
            'methods_attempted': len(results),
            'last_result': results[-1] if results else None
        }
    
    def temporary_unban(self, phone_number, session, analysis):
        """Unban temporarily banned number"""
        
        print(f"[UNBAN] Attempting temporary unban for {phone_number}")
        
        lift_result = self.temp_ban_manager.lift_temp_ban(phone_number)
        if lift_result.get("success"):
            if hasattr(session, '_status'):
                session._status = "active"
            if hasattr(session, '_banned'):
                session._banned = False
            return {
                'success': True,
                'method_used': 'temp_ban_manager_lift',
                'estimated_time': 10,
                'details': lift_result
            }
        
        # Fallback to appeal if no temp ban record found
        result = self._appeal_unban(phone_number, session, "temporary")
        
        if result.get('success'):
            if hasattr(session, '_status'):
                session._status = "active"
            if hasattr(session, '_banned'):
                session._banned = False
            return {
                'success': True,
                'method_used': 'appeal',
                'estimated_time': 60,
                'details': result
            }
        
        # Fallback
        result2 = self._token_reset_unban(phone_number, session, "temporary")
        
        success = result2.get('success', False)
        if success:
            if hasattr(session, '_status'):
                session._status = "active"
            if hasattr(session, '_banned'):
                session._banned = False
        
        return {
            'success': success,
            'method_used': 'token_reset',
            'estimated_time': 60,
            'details': result2,
            'error': '' if success else 'Token reset unban failed — target remains banned'
        }
    
    def _appeal_unban(self, phone_number, session, ban_type):
        """Unban via WhatsApp support appeal automation"""
        
        templates = [
            "My account was hacked. Please restore it.",
            "I was falsely reported. I follow all rules.",
            "Someone else was using my number. Please unban.",
            "It was a misunderstanding. I need my account back.",
            "My business depends on WhatsApp. Please review my case."
        ]
        
        appeal = session.submit_appeal(
            phone_number,
            random.choice(templates),
            evidence={"screenshot": "generated_evidence.png"}
        )
        
        success = appeal.get('accepted', False)
        if success:
            if hasattr(session, '_status'):
                session._status = "active"
            if hasattr(session, '_banned'):
                session._banned = False
        return {
            'method_name': 'appeal_submission',
            'success': success,
            'appeal_id': appeal.get('id'),
            'template_used': templates[-1],
            'error': '' if success else 'Appeal rejected by WhatsApp support'
        }
    
    def _recovery_unban(self, phone_number, session, ban_type):
        """Unban via account recovery workflow"""
        
        recovery = session.initiate_recovery(phone_number)
        
        if recovery.get('sms_required'):
            otp = session.get_virtual_otp(phone_number)
            result = session.complete_recovery(phone_number, otp)
        else:
            result = session.complete_recovery(phone_number)
        
        success = result.get('restored', False)
        if success:
            if hasattr(session, '_status'):
                session._status = "active"
            if hasattr(session, '_banned'):
                session._banned = False
        return {
            'method_name': 'account_recovery',
            'success': success,
            'recovery_type': 'sms_bypass' if recovery.get('sms_required') else 'email',
            'error': '' if success else 'Account recovery failed — OTP/verification rejected'
        }
    
    def _token_reset_unban(self, phone_number, session, ban_type):
        """Unban via WhatsApp token manipulation"""
        
        tokens = session.regenerate_tokens(phone_number)
        registration = session.force_register(phone_number, tokens)
        
        success = registration.get('registered', False)
        if success:
            if hasattr(session, '_status'):
                session._status = "active"
            if hasattr(session, '_banned'):
                session._banned = False
        return {
            'method_name': 'token_reset',
            'success': success,
            'tokens_regenerated': len(tokens),
            'error': '' if success else 'Token reset failed — registration rejected'
        }
    
    def _clone_merge_unban(self, phone_number, session, ban_type):
        """Unban via account cloning and merging"""
        
        clone = session.clone_account(phone_number)
        merge = session.merge_accounts(phone_number, clone['new_number'])
        
        success = merge.get('merged', False)
        if success:
            if hasattr(session, '_status'):
                session._status = "active"
            if hasattr(session, '_banned'):
                session._banned = False
        return {
            'method_name': 'clone_merge',
            'success': success,
            'clone_number': clone.get('new_number'),
            'error': '' if success else 'Clone-merge failed — WhatsApp detected duplication'
        }
    
    def _api_bypass_unban(self, phone_number, session, ban_type):
        """Unban via WhatsApp Business API bypass"""
        
        api = session.get_business_api()
        bypass = api.bypass_restriction(phone_number)
        
        success = bypass.get('unbanned', False)
        if success:
            if hasattr(session, '_status'):
                session._status = "active"
            if hasattr(session, '_banned'):
                session._banned = False
        return {
            'method_name': 'api_bypass',
            'success': success,
            'api_endpoint': bypass.get('endpoint'),
            'error': '' if success else 'Business API bypass failed — restriction still active'
        }
    
    def _verify_unban(self, phone_number, session):
        """Verify if unban was successful"""
        
        checks = session.check_account_status(phone_number)
        
        return {
            'active': checks.get('status') == 'active',
            'current_status': checks.get('status'),
            'can_send_message': checks.get('messaging_allowed', False),
            'profile_accessible': checks.get('profile_visible', False)
        }