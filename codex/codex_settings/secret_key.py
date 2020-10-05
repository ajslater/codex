"""Manage the django secret key."""
from django.core.management.utils import get_random_secret_key


def get_secret_key(config_path):
    """Get the secret key from a file or create and write it."""
    secret_key_path = config_path / "secret_key"
    try:
        with open(secret_key_path, "r") as scf:
            secret_key = scf.read().strip()
    except FileNotFoundError:
        with open(secret_key_path, "w") as scf:
            secret_key = get_random_secret_key()
            scf.write(secret_key)
    return secret_key
