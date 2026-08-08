"""
Ensures required environment variables exist before any test module
imports application code (which reads them once at import time via the
Settings singleton in app/config.py).
"""
import os

from cryptography.fernet import Fernet

os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("APP_DB_HOST", "localhost")
