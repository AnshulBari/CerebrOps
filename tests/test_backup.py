"""
Tests for the CerebrOps backup automation (Phase 5).
"""

import os
import shutil
import sqlite3
import tempfile
import unittest

from scripts.backup import backup_database, copy_models, prune_backups


class TestBackup(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _make_db(self, path, rows=10):
        conn = sqlite3.connect(path)
        try:
            conn.execute("CREATE TABLE metrics (id INTEGER PRIMARY KEY, val REAL)")
            conn.executemany("INSERT INTO metrics (val) VALUES (?)",
                             [(float(i),) for i in range(rows)])
            conn.commit()
        finally:
            conn.close()

    def test_backup_database_creates_snapshot(self):
        src = os.path.join(self._tmp, 'src.db')
        self._make_db(src, rows=25)
        dest = os.path.join(self._tmp, 'backup-1')
        out = backup_database(src, dest)

        self.assertTrue(os.path.exists(out))
        conn = sqlite3.connect(out)
        try:
            n = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 25)

    def test_backup_missing_db_raises(self):
        with self.assertRaises(FileNotFoundError):
            backup_database(os.path.join(self._tmp, 'nope.db'), self._tmp)

    def test_copy_models(self):
        model_dir = os.path.join(self._tmp, 'models')
        os.makedirs(model_dir)
        for name in ('cerebrops_v1.joblib', 'cerebrops_v1_card.json', 'current_version'):
            with open(os.path.join(model_dir, name), 'w') as f:
                f.write(name)
        dest = os.path.join(self._tmp, 'backup-1')
        os.makedirs(dest)
        copied = copy_models(model_dir, dest)
        self.assertEqual(sorted(copied), [
            'cerebrops_v1.joblib', 'cerebrops_v1_card.json', 'current_version',
        ])
        for name in copied:
            self.assertTrue(os.path.exists(os.path.join(dest, name)))

    def test_copy_models_missing_dir_returns_empty(self):
        self.assertEqual(copy_models(os.path.join(self._tmp, 'no-models'), self._tmp), [])

    def test_prune_backups_keeps_newest(self):
        for i in range(5):
            os.makedirs(os.path.join(self._tmp, f'backup-2026081{i}'))
        removed = prune_backups(self._tmp, keep=3)
        remaining = sorted(os.listdir(self._tmp))
        self.assertEqual(len(removed), 2)
        self.assertEqual(len(remaining), 3)
        # Newest three survive.
        self.assertEqual(remaining, ['backup-20260812', 'backup-20260813', 'backup-20260814'])


if __name__ == '__main__':
    unittest.main()
