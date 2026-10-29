#!/usr/bin/env bash
set -euo pipefail
# Compatibility with the existing Isazi Render service startup command.
export DATA_DIR="${DATA_DIR:-/var/data}"
export SECRET_KEY="${SECRET_KEY:-${ISAZI_SECRET_KEY:-}}"
export COOKIE_SECURE="${COOKIE_SECURE:-${ISAZI_HTTPS:-1}}"
export ISAZI_CLIENT_DEMO=0
export DEMO_PAYMENTS_ENABLED="${DEMO_PAYMENTS_ENABLED:-1}"
unset ISAZI_BOOTSTRAP_OWNER_PASSWORD || true
python optimize_assets.py
exec gunicorn --workers 1 --threads 4 --timeout 600 --bind "0.0.0.0:${PORT:-10000}" app:app
