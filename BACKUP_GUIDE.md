# Database Backup Guide

## Overview
The backup system automatically creates timestamped copies of all SQLite databases before operations that could modify data.

## Usage

### Manual Backup
```bash
# Backup all databases
python qnt/backup/db_backup.py backup

# Backup with specific purpose (e.g., before migration)
python qnt/backup/db_backup.py backup pre_migration
```

### List Backups
```bash
python qnt/backup/db_backup.py list
```

### Cleanup Old Backups
```bash
# Remove backups older than 7 days (default)
python qnt/backup/db_backup.py cleanup

# Remove backups older than 30 days
python qnt/backup/db_backup.py cleanup 30
```

### Programmatic Usage
```python
from qnt.backup.db_backup import create_backup, backup_all_databases
from pathlib import Path

# Backup specific database
backup_path = create_backup(
    Path("/path/to/database.db"),
    purpose="pre_update"
)

# Backup all known databases
success = backup_all_databases(purpose="scheduled")
```

## Automatic Integration

Add to your scripts before database operations:

```python
from qnt.backup.db_backup import create_backup
from pathlib import Path

# Before migration/update
db_path = Path("user_data/trades.sqlite")
create_backup(db_path, purpose="pre_migration")

# Now safe to perform operations
```

## Backup Location
Backups are stored in: `qnt/backup/db_backups/`

Naming convention: `{dbname}_{timestamp}_{purpose}.db`

Example: `trades_20250115_143022_pre_migration.db`

## Best Practices
1. Always backup before schema changes
2. Run weekly scheduled backups
3. Keep 7-30 days of backups depending on storage
4. Verify backup integrity after creation
5. Store backups off-site for disaster recovery
