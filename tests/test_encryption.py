import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
from cryptography.fernet import Fernet

os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())

from core.encryption import decrypt_value, encrypt_value  # noqa: E402


def test_encrypt_and_decrypt_round_trip():
    original = "super-secret-db-password"
    encrypted = encrypt_value(original)
    assert encrypted != original
    assert decrypt_value(encrypted) == original


def test_none_and_empty_values_pass_through():
    assert encrypt_value(None) is None
    assert encrypt_value("") is None
    assert decrypt_value(None) is None
    assert decrypt_value("") is None
