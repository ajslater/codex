"""Manage the django secret key and field encryption key."""

import base64
import os

from django.core.management.utils import get_random_secret_key


def get_secret_key(config_path) -> str:
    """Get the secret key from a file or create and write it."""
    secret_key_path = config_path / "secret_key"
    try:
        return secret_key_path.read_text().strip()
    except FileNotFoundError:
        secret_key = get_random_secret_key()
        secret_key_path.write_text(secret_key)
        return secret_key


def get_field_encryption_key(config_path) -> bytes:
    """Get or create a Fernet-compatible 32-byte key for model field encryption."""
    key_path = config_path / "field_encryption_key"
    try:
        return key_path.read_text().strip().encode()
    except FileNotFoundError:
        key = base64.urlsafe_b64encode(os.urandom(32))
        key_path.write_text(key.decode())
        return key
