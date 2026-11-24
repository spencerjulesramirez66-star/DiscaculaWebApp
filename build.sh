#!/usr/bin/env bash
# Render build step (see render.yaml and docs/14-hosting.md). Runs on every deploy.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Free hosting wipes the database file on restart, so re-create the demo accounts each deploy.
if [ "${LOAD_DEMO:-False}" = "True" ]; then
  python manage.py demo
fi
