"""
WSGI config for codex project. Unused. For testing only.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings")

application = get_wsgi_application()


def start_daemons():
    """Delay import until settings environment set."""
    from codex.librarian.daemon import start_daemons

    start_daemons()


start_daemons()
