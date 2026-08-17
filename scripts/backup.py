#!/usr/bin/env python3
"""
CerebrOps backup automation.

Takes a consistent snapshot of the SQLite metrics store (using the sqlite3
online backup API, so the app can keep writing while the backup runs), copies
the persisted model files, writes a manifest, and prunes backups older than
the retention window.

Used by the k8s/base/backup.yaml CronJob and directly for local/offsite backups:
    python scripts/backup.py --db data/cerebrops.db --models-dir models \
        --dest backups --keep 14
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone


def backup_database(db_path: str, dest_dir: str) -> str:
    """Consistent online backup of the SQLite database."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, 'cerebrops.db')
    src = sqlite3.connect(db_path, timeout=30)
    try:
        dst = sqlite3.connect(dest_path)
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()
    return dest_path


def copy_models(model_dir: str, dest_dir: str) -> list:
    """Copy persisted model files (joblib + cards) into the backup dir."""
    copied = []
    if not model_dir or not os.path.isdir(model_dir):
        return copied
    for name in sorted(os.listdir(model_dir)):
        src = os.path.join(model_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dest_dir, name))
            copied.append(name)
    return copied


def prune_backups(root: str, keep: int) -> list:
    """Remove oldest backup dirs beyond `keep`, newest first."""
    backups = sorted(
        (os.path.join(root, n) for n in os.listdir(root)
         if os.path.isdir(os.path.join(root, n)) and n.startswith('backup-')),
        reverse=True,
    )
    removed = []
    for stale in backups[keep:]:
        shutil.rmtree(stale, ignore_errors=True)
        removed.append(os.path.basename(stale))
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description='CerebrOps backup')
    parser.add_argument('--db', default=os.getenv('CEREBROPS_DB_PATH', 'data/cerebrops.db'),
                        help='Path to the SQLite metrics store')
    parser.add_argument('--models-dir', default=os.getenv('CEREBROPS_MODEL_DIR', 'models'),
                        help='Directory with persisted model files')
    parser.add_argument('--dest', default='backups',
                        help='Destination directory (default: backups/)')
    parser.add_argument('--keep', type=int, default=14,
                        help='Number of backups to retain (default: 14)')
    args = parser.parse_args()

    backup_dir = os.path.join(
        args.dest, 'backup-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    )
    try:
        db_path = backup_database(args.db, backup_dir)
        models = copy_models(args.models_dir, backup_dir)
        removed = prune_backups(args.dest, args.keep)
    except Exception as e:
        print(f"ERROR: backup failed: {e}", file=sys.stderr)
        return 1

    manifest = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'database': os.path.basename(db_path),
        'models': models,
        'pruned': removed,
    }
    with open(os.path.join(backup_dir, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"Backup written to {backup_dir}")
    print(f"  database: {manifest['database']}")
    print(f"  models: {len(models)} file(s)")
    if removed:
        print(f"  pruned: {', '.join(removed)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
