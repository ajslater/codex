"""Codex django validators."""
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_path_exists(path):
    if not Path(path).is_dir():
        raise ValidationError(_("%(path)s is not a directory"), params={"path": path})
