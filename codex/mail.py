"""
Codex email backend.

Reads SMTP connection params from the :class:`EmailSettings` singleton
on each :func:`get_connection` call (per Django's mail API), falling
back to :mod:`django.conf.settings` (TOML / env / default). A missing
host short-circuits :meth:`send_messages` to a no-op so feature gates
that fail open do not raise — they are guarded upstream by
:func:`codex.settings.db.email_enabled`.
"""

from typing import override

from django.core.mail.backends.smtp import EmailBackend
from loguru import logger

from codex.settings.db import get_email_connection_kwargs


class DBEmailBackend(EmailBackend):
    """SMTP backend that sources connection params from the DB on init."""

    def __init__(  # noqa: PLR0913 — signature mirrors SMTPBackend.__init__
        self,
        host=None,
        port=None,
        username=None,
        password=None,
        use_tls=None,
        fail_silently=False,  # noqa: FBT002 — kept positional to match parent
        use_ssl=None,
        timeout=None,
        ssl_keyfile=None,
        ssl_certfile=None,
        **kwargs,
    ):
        """Resolve any explicit None to DB → settings before delegating to SMTP."""
        resolved = get_email_connection_kwargs()
        super().__init__(
            host=resolved["host"] if host is None else host,
            port=resolved["port"] if port is None else port,
            username=resolved["username"] if username is None else username,
            password=resolved["password"] if password is None else password,
            use_tls=resolved["use_tls"] if use_tls is None else use_tls,
            fail_silently=fail_silently,
            use_ssl=resolved["use_ssl"] if use_ssl is None else use_ssl,
            timeout=resolved["timeout"] if timeout is None else timeout,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            **kwargs,
        )

    @override
    def send_messages(self, email_messages):
        """No-op when no host is configured rather than raising on open()."""
        if not self.host:
            logger.debug("DBEmailBackend: no host configured, dropping message(s).")
            return 0
        return super().send_messages(email_messages)
