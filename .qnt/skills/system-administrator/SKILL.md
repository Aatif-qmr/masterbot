---
name: system-administrator
description: Manage Cipher infrastructure, deployments, and automation.
---

# System Administrator Skill

Use this skill when performing health checks, managing services, or syncing M1 and M2.

## Core Directives
- **Supervisor Management:** Use `supervisorctl` to manage `freqtrade` and `sentiment` processes.
- **Node Sync:** Always verify M2 connectivity via Tailscale IP `100.74.110.36` before running sync scripts.
- **Dependency Guard:** Never modify `requirements.txt` without testing in a local `venv`.
- **Log Management:** Ensure logs don't fill the disk; verify rotation settings if needed.

## Admin Workflow
1. Run `automation/health_check.py` to get a system-wide status.
2. Check `supervisorctl status` to confirm all processes are `RUNNING`.
3. Verify that `caffeinate` is holding the M1 node awake.
4. Audit `automation/backup.sh` results to ensure Sunday backups are valid.
