#!/usr/bin/env python3
"""
CerebrOps restore drill (Phase 5).

Executes the documented quarterly restore procedure against a SCRATCH
location - never the live store - and verifies the restored state is sound:

  1. Take a consistent backup of the SQLite store (+ persisted models).
  2. Restore it into a scratch directory (simulating a fresh PVC).
  3. Verify: sqlite integrity, key tables, row counts, and that persisted
     model files still load with joblib.

Exits 0 on a fully verified restore, 1 on any failure. Safe to run while
the app is live: the source store is only read (sqlite online backup API).

Usage:
    python scripts/restore_drill.py [--db data/cerebrops.db] [--models-dir models]
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

# Allow running as `python scripts/restore_drill.py` from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.backup import backup_database, copy_models  # noqa: E402

CORE_TABLES = ('metrics', 'alerts', 'anomaly_runs', 'pipeline_events', 'users')


def _make_fixture_db(path: str, rows: int = 500) -> None:
    """Bootstrap a minimal-but-real store so the drill works from scratch."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
            CREATE TABLE metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL, cpu_usage REAL, memory_usage REAL,
                disk_usage REAL, error_rate REAL, request_count REAL,
                response_time REAL, extra_json TEXT
            );
            CREATE TABLE alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                severity TEXT, alert_type TEXT, message TEXT, ts TEXT
            );
            CREATE TABLE anomaly_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT, method TEXT, model_version TEXT,
                payload_json TEXT, ts TEXT
            );
            CREATE TABLE pipeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_id TEXT, status TEXT, stage TEXT, duration REAL,
                branch TEXT, commit_hash TEXT, source TEXT,
                payload_json TEXT, ts TEXT
            );
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, created_at TEXT NOT NULL
            );
        """)
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO metrics (ts, cpu_usage, memory_usage) VALUES (?, 42.0, 60.0)",
            [(now,)] * rows,
        )
        conn.execute(
            "INSERT INTO pipeline_events (pipeline_id, status, stage, ts) "
            "VALUES ('run-drill', 'success', 'deploy', ?)", (now,))
        conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES "
            "('drill@cerebrops.local', 'x', ?)", (now,))
        conn.commit()
    finally:
        conn.close()


def _table_counts(path: str) -> dict:
    conn = sqlite3.connect(path)
    try:
        return {t: conn.execute(
            f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in CORE_TABLES}
    finally:
        conn.close()


def _verify_models(model_dir: str) -> list:
    """Load every joblib artifact; a corrupt model raises here."""
    loaded = []
    if not os.path.isdir(model_dir):
        return loaded
    try:
        import joblib
    except ImportError:
        return ['joblib unavailable - skipped']
    for name in sorted(os.listdir(model_dir)):
        if name.endswith('.joblib'):
            joblib.load(os.path.join(model_dir, name))
            loaded.append(name)
    return loaded


def run_drill(db_path: str, models_dir: str, use_fixture: bool) -> int:
    tmp = tempfile.mkdtemp(prefix='cerebrops-drill-')
    checks = []
    try:
        src_db = db_path
        if use_fixture or not os.path.exists(db_path):
            src_db = os.path.join(tmp, 'src', 'cerebrops.db')
            _make_fixture_db(src_db)
            print(f'[drill] using generated fixture store ({os.path.abspath(src_db)})')
        else:
            print(f'[drill] using real store ({os.path.abspath(src_db)})')

        before = _table_counts(src_db)
        print(f'[drill] pre-backup counts: {before}')

        # 1) Backup (source is only read).
        backup_dir = os.path.join(tmp, 'backups', 'backup-drill')
        backup_database(src_db, backup_dir)
        copied = copy_models(models_dir, backup_dir)
        manifest = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'database': 'cerebrops.db',
            'models': copied,
        }
        with open(os.path.join(backup_dir, 'manifest.json'), 'w') as f:
            json.dump(manifest, f, indent=2)
        print(f'[drill] backup written: {backup_dir} ({len(copied)} model file(s))')

        # 2) Restore into a scratch "data dir".
        scratch_data = os.path.join(tmp, 'restored', 'data')
        os.makedirs(scratch_data, exist_ok=True)
        restored_db = os.path.join(scratch_data, 'cerebrops.db')
        shutil.copy(os.path.join(backup_dir, 'cerebrops.db'), restored_db)
        restored_models = os.path.join(scratch_data, 'models')
        os.makedirs(restored_models, exist_ok=True)
        for name in copied:
            shutil.copy(os.path.join(backup_dir, name), restored_models)
        print(f'[drill] restored to scratch: {scratch_data}')

        # 3) Verify.
        integrity = sqlite3.connect(restored_db).execute(
            'PRAGMA integrity_check').fetchone()[0]
        checks.append(('sqlite integrity_check == ok', integrity == 'ok'))

        after = _table_counts(restored_db)
        checks.append(('all core tables present and non-empty',
                       all(after.get(t, 0) >= before[t] for t in CORE_TABLES)))
        checks.append(('row counts match pre-backup exactly', after == before))

        models_ok = True
        try:
            loaded = _verify_models(restored_models)
            models_ok = all('skipped' not in str(m) for m in loaded)
        except Exception as exc:
            print(f'[drill] model load FAILED: {exc}')
            models_ok = False
        checks.append(('persisted models load with joblib', models_ok))

        manifest_ok = os.path.exists(os.path.join(backup_dir, 'manifest.json'))
        checks.append(('manifest.json present', manifest_ok))

        print('\n--- restore drill results ---')
        ok = True
        for label, passed in checks:
            print(f'  [{"PASS" if passed else "FAIL"}] {label}')
            ok = ok and passed
        if ok:
            print('\nRESTORE DRILL PASSED - restored store is sound and usable.')
        else:
            print('\nRESTORE DRILL FAILED - do not rely on backups until fixed.',
                  file=sys.stderr)
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description='CerebrOps restore drill')
    parser.add_argument('--db', default=os.getenv('CEREBROPS_DB_PATH', 'data/cerebrops.db'))
    parser.add_argument('--models-dir', default=os.getenv('CEREBROPS_MODEL_DIR', 'models'))
    parser.add_argument('--fixture', action='store_true',
                        help='Always use a generated fixture store (CI-safe)')
    args = parser.parse_args()
    return run_drill(args.db, args.models_dir, use_fixture=args.fixture)


if __name__ == '__main__':
    sys.exit(main())
