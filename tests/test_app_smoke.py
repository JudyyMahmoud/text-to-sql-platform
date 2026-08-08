"""
Full integration tests (connection testing, schema discovery, file
processing, database/document/hybrid chat) require the docker-compose
stack running (Postgres + the sample customer DB) and a valid
OPENAI_API_KEY, since they exercise the real LLM and real databases.

Run them with the stack up:
    docker compose up -d
    pip install -r requirements.txt
    pytest tests/ -v

This file just verifies the FastAPI app boots and its routes are wired
correctly, which does not require any external services.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
from cryptography.fernet import Fernet

os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "docs" in response.json()


def test_unauthenticated_request_is_rejected():
    response = client.get("/api/database-connections")
    assert response.status_code == 401
