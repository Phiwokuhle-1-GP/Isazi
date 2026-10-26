#!/usr/bin/env bash
set -euo pipefail
# Database lives on Render's attached persistent disk, configured in render.yaml.
python deploy_bootstrap.py
# Do not pass the setup password to the live web server process.
unset ISAZI_BOOTSTRAP_OWNER_PASSWORD || true
exec waitress-serve --host=0.0.0.0 --port="${PORT:-10000}" wsgi:app
