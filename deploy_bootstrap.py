"""One-time, non-interactive Render bootstrap.

This never prints passwords. It creates an owner account only for a *new*, empty
users table. An existing database (including accounts and revision history) is
always left untouched.
"""
import os
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from app import create_app


def bootstrap():
    app = create_app()
    store = app.extensions['isazi_store']
    with store.connect() as conn:
        count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if count:
        print('Isazi database initialized. Existing owner accounts preserved.')
        return
    password = os.environ.get('ISAZI_BOOTSTRAP_OWNER_PASSWORD', '')
    if len(password) < 12:
        raise SystemExit(
            'First deployment requires a private ISAZI_BOOTSTRAP_OWNER_PASSWORD '
            'environment variable of at least 12 characters. Set it in Render, '
            'then redeploy. Do not commit or paste the password into source code.'
        )
    with store.connect() as conn:
        # Guard again to avoid duplicate accounts on concurrent starts.
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
            return
        conn.execute('''INSERT INTO users(username,password_hash,role,enabled,created_at)
                        VALUES (?,?,?,?,?)''',
                     ('owner', generate_password_hash(password), 'admin', 1,
                      datetime.now(timezone.utc).isoformat(timespec='seconds')))
    print('Isazi owner account created on persistent database. Username: owner.')


if __name__ == '__main__':
    bootstrap()
