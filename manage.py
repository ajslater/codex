#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run the server."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        reason = (
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        )
        raise ImportError(reason) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
