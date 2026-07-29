#!/bin/sh
set -e

if [ "${SERVICE_ROLE}" = "worker" ]; then
  exec arq app.workers.settings.WorkerSettings
fi

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
