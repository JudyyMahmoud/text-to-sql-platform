"""
Encrypts/decrypts sensitive values (customer database passwords and
connection strings) before they are stored in the platform database.
Uses Fernet symmetric encryption (AES128-CBC + HMAC).
"""
from cryptography.fernet import Fernet

from app.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            raise RuntimeError(
                "ENCRYPTION_KEY is not set. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_value(plain_text: str | None) -> str | None:
    if plain_text is None or plain_text == "":
        return None
    return _get_fernet().encrypt(plain_text.encode()).decode()


def decrypt_value(cipher_text: str | None) -> str | None:
    if cipher_text is None or cipher_text == "":
        return None
    return _get_fernet().decrypt(cipher_text.encode()).decode()
