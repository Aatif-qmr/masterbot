import os
import sys
import sqlite3
import psycopg
from pathlib import Path

# Resolve base directories
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'freqtrade'))

# Database configurations
DB_MAPS = {
    "mean_reversion": {
        "sqlite": str(BASE_DIR / 'user_data' / 'mean_reversion.sqlite'),
        "postgres_db": "cipher_mean_reversion"
    },
    "trend_follow": {
        "sqlite": str(BASE_DIR / 'user_data' / 'trend_follow.sqlite'),
        "postgres_db": "cipher_trend_follow"
    },
    "scalp": {
        "sqlite": str(BASE_DIR / 'user_data' / 'scalp.sqlite'),
        "postgres_db": "cipher_scalp"
    },
    "swing": {
        "sqlite": str(BASE_DIR / 'user_data' / 'swing.sqlite'),
        "postgres_db": "cipher_swing"
    },
    "daily": {
        "sqlite": str(BASE_DIR / 'user_data' / 'daily.sqlite'),
        "postgres_db": "cipher_daily"
    },
    "micro": {
        "sqlite": str(BASE_DIR / 'user_data' / 'tradesv3_micro.sqlite'),
        "postgres_db": "cipher_micro"
    },
    "bear_scalp": {
        "sqlite": str(BASE_DIR / 'user_data' / 'bear_scalp.sqlite'),
        "postgres_db": "cipher_bear_scalp"
    },
    "hyperliquid": {
        "sqlite": str(BASE_DIR / 'user_data' / 'hyperliquid.sqlite'),
        "postgres_db": "cipher_hyperliquid"
    }
}

# In Freqtrade, these are the persistent tables
# We list them in dependency order: parent tables first, child tables last
TABLES_TO_MIGRATE = [
    "KeyValueStore",
    "wallet_history",
    "pairlocks",
    "trades",
    "orders",
    "trade_custom_data"
]

def create_postgres_db(db_name: str):
    """Creates the target PostgreSQL database if it does not exist."""
    print(f"Connecting to default postgres db to ensure '{db_name}' exists...")
    conn = psycopg.connect(dbname="postgres", user="aatifquamre", host="localhost", autocommit=True)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_name,))
    exists = cursor.fetchone()
    if not exists:
        print(f"Creating database '{db_name}'...")
        cursor.execute(f"CREATE DATABASE {db_name}")
    else:
        print(f"Database '{db_name}' already exists.")
    
    cursor.close()
    conn.close()

def initialize_freqtrade_schema(db_url: str):
    """Initializes the database schema using Freqtrade's own persistence initialization."""
    print(f"Initializing Freqtrade DB schema via init_db on: {db_url}")
    from freqtrade.persistence import init_db
    # This will create all tables, primary keys, indexes and run migrations
    init_db(db_url)

def clean_postgres_tables(pg_conn):
    """Cleans existing rows in target tables in reverse dependency order."""
    cursor = pg_conn.cursor()
    print("Truncating existing tables to avoid duplicate constraint failures...")
    for table in reversed(TABLES_TO_MIGRATE):
        try:
            # Check if table exists in postgres first
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (table,))
            if cursor.fetchone()[0]:
                cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE')
        except Exception as e:
            print(f"Warning during truncate of {table}: {e}")
            pg_conn.rollback()
    pg_conn.commit()
    cursor.close()

def get_boolean_columns(pg_conn, table_name: str) -> set:
    """Queries Postgres schema to find all columns of type 'boolean' for the given table."""
    cursor = pg_conn.cursor()
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s AND data_type = 'boolean'",
        (table_name,)
    )
    cols = {row[0].lower() for row in cursor.fetchall()}
    cursor.close()
    return cols

def migrate_table(sqlite_conn, pg_conn, table_name: str):
    """Migrates rows of a specific table from SQLite to PostgreSQL."""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Check if table exists in sqlite
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not sqlite_cursor.fetchone():
        print(f"Table '{table_name}' does not exist in SQLite source. Skipping.")
        return

    # Fetch rows and column names from SQLite
    sqlite_cursor.execute(f'SELECT * FROM "{table_name}"')
    rows = sqlite_cursor.fetchall()
    if not rows:
        print(f"Table '{table_name}' is empty. Skipping copy.")
        return

    columns = [description[0] for description in sqlite_cursor.description]
    bool_cols = get_boolean_columns(pg_conn, table_name)
    if bool_cols:
        print(f"Detected boolean columns in '{table_name}': {bool_cols}")

    # Build insert query for Postgres
    col_str = ", ".join(f'"{col.lower()}"' for col in columns)
    val_placeholders = ", ".join(["%s"] * len(columns))
    insert_query = f'INSERT INTO "{table_name}" ({col_str}) VALUES ({val_placeholders})'
    
    print(f"Migrating {len(rows)} rows for table '{table_name}'...")
    for row in rows:
        pg_row = []
        for col_name, val in zip(columns, row):
            if col_name.lower() in bool_cols:
                # Convert SQLite 1/0 integer to True/False for Postgres
                pg_row.append(bool(val) if val is not None else None)
            else:
                pg_row.append(val)
        pg_cursor.execute(insert_query, tuple(pg_row))
        
    pg_conn.commit()
    sqlite_cursor.close()
    pg_cursor.close()

def reset_sequences(pg_conn):
    """Resets the serial auto-increment sequences in Postgres to prevent primary key conflicts."""
    print("Resetting primary key auto-increment sequences...")
    cursor = pg_conn.cursor()
    # List of tables that have serial primary keys
    tables_with_id = ["trades", "orders", "wallet_history", "pairlocks", "trade_custom_data"]
    for table in tables_with_id:
        try:
            cursor.execute(f'SELECT MAX(id) FROM "{table}"')
            max_id = cursor.fetchone()[0]
            if max_id is not None:
                seq_name = f"{table}_id_seq"
                cursor.execute(f"SELECT setval('{seq_name}', %s)", (max_id,))
                print(f"Sequence reset for table '{table}': next val > {max_id}")
        except Exception as e:
            print(f"Warning resetting sequence for {table}: {e}")
            pg_conn.rollback()
    pg_conn.commit()
    cursor.close()

def main():
    print("=== Cipher Database Migration (SQLite -> PostgreSQL) ===")
    
    for strategy_name, config in DB_MAPS.items():
        print(f"\n>>> Processing Strategy: {strategy_name.upper()} <<<")
        sqlite_path = config["sqlite"]
        db_name = config["postgres_db"]
        db_url = f"postgresql://aatifquamre@localhost/{db_name}"
        
        if not os.path.exists(sqlite_path):
            print(f"SQLite file '{sqlite_path}' not found. Skipping strategy.")
            continue
            
        # 1. Create database in Postgres
        try:
            create_postgres_db(db_name)
        except Exception as e:
            print(f"Error creating database '{db_name}': {e}")
            continue
            
        # 2. Initialize Freqtrade Schema in Postgres
        try:
            initialize_freqtrade_schema(db_url)
        except Exception as e:
            print(f"Error initializing schema for '{db_name}': {e}")
            continue
            
        # 3. Migrate data
        try:
            sqlite_conn = sqlite3.connect(sqlite_path)
            pg_conn = psycopg.connect(db_url)
            
            # Clean tables first
            clean_postgres_tables(pg_conn)
            
            # Copy data for each table
            for table in TABLES_TO_MIGRATE:
                migrate_table(sqlite_conn, pg_conn, table)
                
            # Reset sequences
            reset_sequences(pg_conn)
            
            sqlite_conn.close()
            pg_conn.close()
            print(f"✓ Strategy '{strategy_name}' migrated successfully.")
        except Exception as e:
            print(f"Critical error migrating '{strategy_name}': {e}")
            
    print("\n=== Database Migration Complete ===")

if __name__ == "__main__":
    main()
