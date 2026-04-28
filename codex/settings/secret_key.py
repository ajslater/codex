"""Manage the django secret key."""

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
