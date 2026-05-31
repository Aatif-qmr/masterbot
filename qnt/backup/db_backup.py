#!/usr/bin/env python3
"""
Database Backup Utility
Creates timestamped backups of SQLite databases before operations
"""

import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

# Get base directory from environment or use default
BASE_DIR = Path(os.environ.get("CIPHER_DIR", Path.home() / "cipher"))
VAULT_DB = BASE_DIR / "qnt" / "vault" / "vault.db"
MEMORY_DB = BASE_DIR / "qnt" / "memory" / "memory.db"
TRADES_DB = BASE_DIR / "user_data" / "trades.sqlite"

BACKUP_DIR = BASE_DIR / "qnt" / "backup" / "db_backups"


def ensure_backup_dir():
    """Create backup directory if it doesn't exist"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def create_backup(db_path: Path, purpose: str = "manual") -> Path:
    """
    Create a timestamped backup of a SQLite database

    Args:
        db_path: Path to the SQLite database file
        purpose: Reason for backup (e.g., "pre_migration", "pre_update")

    Returns:
        Path to the backup file, or None if backup failed
    """
    if not db_path.exists():
        print(f"[BACKUP] Database not found: {db_path}")
        return None

    ensure_backup_dir()

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_name = f"{db_path.stem}_{timestamp}_{purpose}.db"
    backup_path = BACKUP_DIR / backup_name

    try:
        # Close any active connections by copying the file
        shutil.copy2(db_path, backup_path)

        # Verify backup integrity
        conn = sqlite3.connect(str(backup_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        conn.close()

        if result == "ok":
            print(f"[BACKUP] Successfully created: {backup_path}")
            print(f"[BACKUP] Size: {backup_path.stat().st_size / 1024:.2f} KB")
            return backup_path
        else:
            print(f"[BACKUP] ERROR: Backup integrity check failed: {result}")
            backup_path.unlink(missing_ok=True)
            return None

    except Exception as e:
        print(f"[BACKUP] ERROR creating backup: {e}")
        if backup_path.exists():
            backup_path.unlink(missing_ok=True)
        return None


def backup_all_databases(purpose: str = "manual"):
    """Backup all known databases"""
    print(f"[BACKUP] Starting backup of all databases (purpose: {purpose})")

    databases = [VAULT_DB, MEMORY_DB, TRADES_DB]
    successful = []
    failed = []

    for db_path in databases:
        if db_path.exists():
            result = create_backup(db_path, purpose)
            if result:
                successful.append(str(db_path))
            else:
                failed.append(str(db_path))
        else:
            print(f"[BACKUP] Skipping (not found): {db_path}")

    print("\n[BACKUP] Summary:")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")

    if failed:
        print(f"  Failed databases: {', '.join(failed)}")

    return len(failed) == 0


def cleanup_old_backups(days_to_keep: int = 7):
    """Remove backups older than specified days"""
    if not BACKUP_DIR.exists():
        return

    cutoff = datetime.now(UTC).timestamp() - (days_to_keep * 24 * 60 * 60)
    removed = 0

    for backup_file in BACKUP_DIR.glob("*.db"):
        if backup_file.stat().st_mtime < cutoff:
            try:
                backup_file.unlink()
                print(f"[BACKUP] Removed old backup: {backup_file.name}")
                removed += 1
            except Exception as e:
                print(f"[BACKUP] ERROR removing {backup_file.name}: {e}")

    print(f"[BACKUP] Cleaned up {removed} old backups")


def list_backups(limit: int = 10):
    """List recent backups"""
    if not BACKUP_DIR.exists():
        print("[BACKUP] No backup directory found")
        return []

    backups = sorted(BACKUP_DIR.glob("*.db"), key=lambda x: x.stat().st_mtime, reverse=True)

    print(f"\nRecent Backups (showing {min(len(backups), limit)} of {len(backups)}):")
    print("-" * 80)

    for i, backup in enumerate(backups[:limit]):
        size_kb = backup.stat().st_size / 1024
        mtime = datetime.fromtimestamp(backup.stat().st_mtime, tz=UTC)
        print(f"{i + 1}. {backup.name}")
        print(f"   Created: {mtime.isoformat()}")
        print(f"   Size: {size_kb:.2f} KB")
        print()

    return backups[:limit]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "backup":
            purpose = sys.argv[2] if len(sys.argv) > 2 else "manual"
            backup_all_databases(purpose)

        elif command == "list":
            list_backups()

        elif command == "cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            cleanup_old_backups(days)

        else:
            print(f"Unknown command: {command}")
            print("Usage: python db_backup.py [backup|list|cleanup] [args]")
    else:
        # Default: create backup
        backup_all_databases("scheduled")
