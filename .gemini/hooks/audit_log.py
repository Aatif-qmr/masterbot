import sys
import os
import subprocess
from datetime import datetime

# Configuration
LOG_DOC_ID = '1N1Mk2z4WYtWAd9JU1VK52HeLu3IqucBHA2_ZBHvZasQ'

def log_change(author, action, rationale):
    # Use Local Time for the user's convenience (Asia/Calcutta)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format as a clean Markdown-style block for Google Docs
    block = f"""
---
### {date_str} | {author}
**Action:** {action}
**Rationale:** {rationale}
"""
    
    # We use a specific instruction to the assistant to ensure it applies formatting
    prompt = f"Append this entry to the Google Doc '{LOG_DOC_ID}'. Format the first line as a Heading and ensure the Action/Rationale labels are Bold: {block}"
    
    try:
        # Run via qnt -p
        subprocess.run(['qnt', '-p', prompt], check=True, capture_output=True)
    except Exception as e:
        with open('logs/audit_errors.log', 'a') as f:
            f.write(f"{date_str} - Failed to log: {str(e)}\n")

if __name__ == "__main__":
    if len(sys.argv) > 3:
        log_change(sys.argv[1], sys.argv[2], sys.argv[3])
