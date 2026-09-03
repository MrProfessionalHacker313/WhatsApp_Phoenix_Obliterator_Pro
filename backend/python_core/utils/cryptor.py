from __future__ import annotations

from cryptography.fernet import Fernet


class Cryptor:
    """Utility for protecting sensitive evidence payloads at rest."""

    def __init__(self, key: str | None = None):
        self.key = key or Fernet.generate_key()
        self.fernet = Fernet(self.key)

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
