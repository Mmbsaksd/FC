"""
Automated Database Backup and Recovery Utility for Personal Windows Environment.
Performs atomic SQLite backups, JSON snapshot exports, and integrity verification.
"""

import os
import sys
import shutil
import sqlite3
import logging
from datetime import datetime, timezone

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.storage.sqlite_manager import DB_PATH, DB_DIRECTORY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DBBackup")

BACKUP_DIR = os.path.join(DB_DIRECTORY, "backups")

def create_backup(backup_tag: str = "auto") -> str:
    """Creates a point-in-time atomic copy of the SQLite database."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"trading_system_{backup_tag}_{timestamp}.db")

    if not os.path.exists(DB_PATH):
        logger.warning(f"Database {DB_PATH} does not exist yet. Nothing to backup.")
        return ""

    try:
        # Use SQLite Online Backup API for 100% atomic point-in-time copy without locking writers
        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(backup_file)
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        dst_conn.close()
        src_conn.close()

        file_size_kb = round(os.path.getsize(backup_file) / 1024.0, 2)
        logger.info(f"✅ SQLite atomic backup successfully created: {backup_file} ({file_size_kb} KB)")
        return backup_file
    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        return ""

def restore_backup(backup_file_path: str) -> bool:
    """Restores database from a specific backup file."""
    if not os.path.exists(backup_file_path):
        logger.error(f"Backup file {backup_file_path} not found.")
        return False

    try:
        # Verify integrity of backup first
        test_conn = sqlite3.connect(backup_file_path)
        cur = test_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()[0]
        test_conn.close()

        if res != "ok":
            logger.error(f"Backup file corrupted: {res}")
            return False

        # Create temporary safety copy of existing DB before replacing
        if os.path.exists(DB_PATH):
            safety_copy = f"{DB_PATH}.pre_restore_bak"
            shutil.copy2(DB_PATH, safety_copy)

        shutil.copy2(backup_file_path, DB_PATH)
        logger.info(f"✅ Database restored successfully from {backup_file_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Restore failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--restore":
        if len(sys.argv) > 2:
            restore_backup(sys.argv[2])
        else:
            print("Usage: python scripts/backup_database.py --restore <path_to_backup.db>")
    else:
        create_backup(backup_tag="manual")
