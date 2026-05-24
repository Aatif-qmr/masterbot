import os
import sys
import time
from enum import IntEnum

# Add memory dir to path for imports
sys.path.insert(0, '/Users/aatifquamre/cipher/qnt/memory')
from memory_manager import log_action, log_decision, update_decision_outcome
from qnt_notifier import send_notify, send_escalation, get_pending_reply, parse_reply

class AutonomyLevel(IntEnum):
    SILENT = 0
    NOTIFY = 1
    ESCALATE = 2

def classify(situation_type, context=None):
    """
    Classifies a situation into an autonomy level.
    Returns: (level, reasoning)
    """
    
    # SILENT Rules
    if situation_type in [
        "routine_sync", "log_rotation", "minor_param_adj",
        "normal_sentiment_change", "quota_switch", "scheduled_task_ok"
    ]:
        return AutonomyLevel.SILENT, "Routine maintenance task."

    # NOTIFY Rules
    if situation_type in [
        "freqai_retrained", "hyperopt_improvement", "strategy_discovered",
        "report_generated", "sync_restored", "risk_level_change",
        "position_size_auto_adj", "notable_task_result", "routine_maintenance"
    ]:
        return AutonomyLevel.NOTIFY, "Informational event, no input needed."

    # ESCALATE Rules
    if situation_type in [
        "consecutive_losses", "drawdown_limit_near", "quota_exhausted",
        "diagnosis_failed", "strategy_deployment", "security_failure",
        "freqtrade_down_recovery_failed", "m2_unreachable", "unknown_situation"
    ]:
        return AutonomyLevel.ESCALATE, "Critical event or decision requiring authorization."

    # Default to escalation for safety
    return AutonomyLevel.ESCALATE, "Unclassified situation, defaulting to safety."

def handle(situation_type, context, action_fn, 
           notify_title=None, notify_message=None,
           escalation_options=None, recommendation=None):
    """
    Master handler for autonomous actions.
    """
    level, reasoning = classify(situation_type, context)
    
    if level == AutonomyLevel.SILENT:
        # Just act and log
        result = action_fn()
        log_action(f"auto_{situation_type}", f"Result: {result} (Silent). Reason: {reasoning}")
        return result

    if level == AutonomyLevel.NOTIFY:
        # Act, log, and notify
        result = action_fn()
        log_action(f"auto_{situation_type}", f"Result: {result} (Notified). Reason: {reasoning}")
        
        title = notify_title or f"Action: {situation_type}"
        msg = notify_message or f"QNT completed {situation_type} automatically.\nContext: {context}"
        send_notify(title, msg)
        return result

    if level == AutonomyLevel.ESCALATE:
        # Pause, log decision, escalate, wait
        print(f"ESCALATING: {situation_type}")
        
        # log_decision happens inside send_escalation
        msg_id = send_escalation(
            situation=situation_type,
            options=escalation_options or ["Proceed", "Abort"],
            recommendation=recommendation or "Proceed cautiously.",
            context=context
        )
        
        if not msg_id:
            # Fallback if Telegram fails
            log_action(f"escalation_failed", f"Could not send Telegram for {situation_type}")
            return None
            
        # Wait for reply (blocking call)
        reply_text = get_pending_reply(timeout_minutes=30)
        
        if not reply_text:
            log_action(f"escalation_timeout", f"No reply for {situation_type} after 30m")
            return None
            
        parsed = parse_reply(reply_text, len(escalation_options) if escalation_options else 2)
        
        # Execute based on choice or custom
        # For simplicity in this base version, we assume action_fn can take the choice
        result = action_fn(parsed)
        
        # Log outcome
        # timestamp is not easily available here, normally we'd pass it back
        # update_decision_outcome(ts, f"Executed: {result}")
        
        return result

if __name__ == "__main__":
    # Test classification
    lvl, r = classify("routine_sync")
    print(f"Sync: {AutonomyLevel(lvl).name} - {r}")
    
    lvl, r = classify("strategy_deployment")
    print(f"Deploy: {AutonomyLevel(lvl).name} - {r}")
