# Cipher Project Mandates

## Core Identity
This is the Cipher trading system intelligence layer. All agents (Gemini CLI or QNT CLI) must adhere to these rules.

## Tool Permissions
- **YOLO Mode:** All agents are authorized to operate in YOLO/Permission-free mode for standard shell utilities (`cat`, `ls`, `grep`, `find`, `for`, `echo`, `head`, `tail`, `wc`).
- **Policy Files:** Refer to `.qnt/policies/cipher.toml` and `.gemini/policies/cipher.toml` for high-priority allow rules.

## Mandatory Audit Logging
- **The Rule:** Every modification to the source code, strategies, or configurations MUST be logged in the **[Cipher System Audit Log](https://docs.google.com/document/d/1N1Mk2z4WYtWAd9JU1VK52HeLu3IqucBHA2_ZBHvZasQ/edit)**.
- **The Tool:** Use the shared utility script at `.qnt/hooks/audit_log.py` or `.gemini/hooks/audit_log.py`.
- **The Format:** `python3 .qnt/hooks/audit_log.py "AgentName" "What was changed" "Why it was changed"`

## Intelligence & Reporting
- **Intelligent Reporter:** A Mistral-powered reporting pipeline is available at `automation/intelligent_reporter.py`.
- **Function:** Aggregates data from all SQLite DBs, performs LLM analysis using Mistral Free Tier, creates Google Doc reports, and sends Telegram alerts.
- **Execution:** Run via `python3 automation/intelligent_reporter.py`.
- **Rate Limits:** Uses `tenacity` for retries to respect Mistral's 1 RPS limit on the free tier.
- **Owner Account:** `aatifqmr@gmail.com`
- **Reports Folder:** `1Vdst3YI9wFFfFPurpVVGJfrA3y2aT9BI` (Cipher_Vault/Reports)
- **Automated Reporter:** Trigger `python3 automation/workspace_reporter.py` for aggregated performance summaries.

## Database Access
- Primary trade data is distributed across multiple SQLite files in `user_data/` (e.g., `micro.sqlite`, `scalp.sqlite`, `mean_reversion.sqlite`).
- Use the **SQLite MCP Server** for autonomous querying.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read graphify-out/GRAPH_REPORT.md before reading any source files, running grep/glob searches, or answering codebase questions. The graph is your primary map of the codebase.
- IF graphify-out/wiki/index.md EXISTS, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
