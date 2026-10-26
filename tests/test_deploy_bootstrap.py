"""Bootstrap needs Flask; integration tests run with app requirements installed."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('flask') is not None, 'Install Flask for deployment tests')
class BootstrapTests(unittest.TestCase):
    def test_one_time_owner_creation_and_idempotence(self):
        from deploy_bootstrap import bootstrap
        from app import create_app
        with tempfile.TemporaryDirectory() as tmp:
            env = {'ISAZI_DB_PATH': str(Path(tmp) / 'isazi.sqlite3'),
                   'ISAZI_SECRET_KEY': 'unit-test-only',
                   'ISAZI_BOOTSTRAP_OWNER_PASSWORD': 'unique-test-bootstrap-password'}
            with patch.dict(os.environ, env):
                bootstrap()
                app = create_app()
                with app.extensions['isazi_store'].connect() as c:
                    first = c.execute('SELECT id,password_hash FROM users WHERE username=?', ('owner',)).fetchone()
                    self.assertIsNotNone(first)
                bootstrap()
                with app.extensions['isazi_store'].connect() as c:
                    count = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
                    self.assertEqual(count, 1)

    def test_requires_private_password_on_empty_db(self):
        from deploy_bootstrap import bootstrap
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'ISAZI_DB_PATH': str(Path(tmp) / 'isazi.sqlite3'),
                                         'ISAZI_SECRET_KEY': 'unit-test-only'}, clear=True):
                with self.assertRaises(SystemExit):
                    bootstrap()

if __name__ == '__main__':
    unittest.main()
