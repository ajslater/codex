"""Restarter Status Types."""

from django.db.models import TextChoices


class CodexRestarterStatusTypes(TextChoices):
    """Janitor Status Types."""

    CODEX_RESTART = "RCR"
    CODEX_STOP = "RCS"
