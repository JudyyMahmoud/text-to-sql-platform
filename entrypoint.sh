#!/bin/bash
set -e

echo "Waiting for the application database to be ready..."
python scripts/wait_for_db.py

echo "Running database migrations..."
alembic upgrade head

echo "Seeding a default tenant/admin user if none exists..."
python scripts/init_db.py

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
