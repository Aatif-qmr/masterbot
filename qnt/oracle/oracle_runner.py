import sys
import os

# Add paths
BASE_DIR = '/Users/aatifquamre/masterbot'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/oracle'))

from oracle_calendar import check_and_act as calendar_check
from oracle_sentiment import check_and_act as sentiment_check
from oracle_anomaly import run_all_anomaly_checks
from memory_manager import log_action, get_device_identity

def run(mode='all'):
    device = get_device_identity()
    
    if mode == 'calendar' or mode == 'all':
        try:
            calendar_check()
            log_action('oracle_calendar_check', 'completed', device['device'])
        except Exception as e:
            print(f"Error in calendar check: {e}")
    
    if mode == 'sentiment' or mode == 'all':
        try:
            sentiment_check()
            log_action('oracle_sentiment_check', 'completed', device['device'])
        except Exception as e:
            print(f"Error in sentiment check: {e}")
    
    if mode == 'anomaly' or mode == 'all':
        try:
            run_all_anomaly_checks()
            log_action('oracle_anomaly_check', 'completed', device['device'])
        except Exception as e:
            print(f"Error in anomaly check: {e}")

if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    run(mode)
