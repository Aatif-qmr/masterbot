# MasterBot Project Mandates

## Core Identity
This is the MasterBot trading system intelligence layer. All agents (Gemini CLI or QNT CLI) must adhere to these rules.

## Tool Permissions
- **YOLO Mode:** All agents are authorized to operate in YOLO/Permission-free mode for standard shell utilities (`cat`, `ls`, `grep`, `find`, `for`, `echo`, `head`, `tail`, `wc`).
- **Policy Files:** Refer to `.qnt/policies/masterbot.toml` and `.gemini/policies/masterbot.toml` for high-priority allow rules.

## Mandatory Audit Logging
- **The Rule:** Every modification to the source code, strategies, or configurations MUST be logged in the **[MasterBot System Audit Log](https://docs.google.com/document/d/1N1Mk2z4WYtWAd9JU1VK52HeLu3IqucBHA2_ZBHvZasQ/edit)**.
- **The Tool:** Use the shared utility script at `.qnt/hooks/audit_log.py` or `.gemini/hooks/audit_log.py`.
- **The Format:** `python3 .qnt/hooks/audit_log.py "AgentName" "What was changed" "Why it was changed"`

## Google Workspace Integration
- **Owner Account:** `aatifqmr@gmail.com`
- **Reports Folder:** `1Vdst3YI9wFFfFPurpVVGJfrA3y2aT9BI` (MasterBot_Vault/Reports)
- **Automated Reporter:** Trigger `python3 automation/workspace_reporter.py` for aggregated performance summaries.

## Database Access
- Primary trade data is distributed across multiple SQLite files in `user_data/` (e.g., `micro.sqlite`, `scalp.sqlite`, `mean_reversion.sqlite`).
- Use the **SQLite MCP Server** for autonomous querying.
