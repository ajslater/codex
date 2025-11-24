"""Library model."""

from datetime import timedelta
from pathlib import Path
from types import MappingProxyType

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CharField,
    DateTimeField,
    DurationField,
    ManyToManyField,
)
from django.utils.translation import gettext_lazy as _
from typing_extensions import override

from codex.models.base import MAX_PATH_LEN, BaseModel

__all__ = ("Library", "validate_dir_exists")


def validate_dir_exists(path):
    """Validate that a library exists."""
    if not Path(path).is_dir():
        raise ValidationError(_("{path} is not a directory"), params={"path": path})


class Library(BaseModel):
    """The library comic file live under."""

    DEFAULT_POLL_EVERY_SECONDS = 60 * 60
    DEFAULT_POLL_EVERY = timedelta(seconds=DEFAULT_POLL_EVERY_SECONDS)
    CUSTOM_COVERS_DIR_DEFAULTS = MappingProxyType(
        {
            "covers_only": True,
            "events": False,
            "poll": False,
        }
    )
    covers_only = BooleanField(db_index=True, default=False)
    path = CharField(
        unique=True,
        db_index=True,
        max_length=MAX_PATH_LEN,
        validators=[validate_dir_exists],
    )
    events = BooleanField(db_index=True, default=True)
    poll = BooleanField(db_index=True, default=True)
    poll_every = DurationField(default=DEFAULT_POLL_EVERY)
    last_poll = DateTimeField(null=True)
    update_in_progress = BooleanField(default=False)
    groups = ManyToManyField(Group, blank=True)

    @override
    def __repr__(self) -> str:
        """Return the path."""
        return str(self.path)

    class Meta(BaseModel.Meta):
        """Pluralize."""

        verbose_name_plural = "Libraries"

    def _save_update_in_progress(self, *, value: bool):
        self.update_in_progress = value
        self.save(update_fields=["update_in_progress"])

    def start_update(self):
        """Start a library update."""
        self._save_update_in_progress(value=True)

    def end_update(self):
        """Finish a library update."""
        self._save_update_in_progress(value=False)
