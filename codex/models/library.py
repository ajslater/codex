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

from codex.models.base import BaseModel

__all__ = ("Library", "validate_dir_exists")

MAX_PATH_LEN = 4095


def validate_dir_exists(path):
    """Validate that a library exists."""
    if not Path(path).is_dir():
        raise ValidationError(_(f"{path} is not a directory"), params={"path": path})


class RootDirBase(BaseModel):
    DEFAULT_POLL_EVERY_SECONDS = 60 * 60
    DEFAULT_POLL_EVERY = timedelta(seconds=DEFAULT_POLL_EVERY_SECONDS)

    events = BooleanField(db_index=True, default=True)
    poll = BooleanField(db_index=True, default=True)
    poll_every = DurationField(default=DEFAULT_POLL_EVERY)
    last_poll = DateTimeField(null=True)
    update_in_progress = BooleanField(default=False)

    class Meta(BaseModel.Meta):
        """Abstract class."""

        abstract = True


class Library(RootDirBase):
    """The library comic file live under."""

    path = CharField(
        unique=True,
        db_index=True,
        max_length=MAX_PATH_LEN,
        validators=[validate_dir_exists],
    )
    groups = ManyToManyField(Group, blank=True)

    def __str__(self):
        """Return the path."""
        return self.path

    class Meta(RootDirBase.Meta):
        """Pluralize."""

        verbose_name_plural = "Libraries"


class CustomCoverDir(RootDirBase):
    CHILD_PATHS = ("publishers", "imprints", "series", "story-arcs")
    DEFAULTS = MappingProxyType(
        {
            "pk": 1,
            "events": False,
            "poll": False,
        }
    )

    @property
    def path(self):
        from settings.settings import CONFIG_PATH

        return CONFIG_PATH / "custom-covers"

    def save(self, *args, **kwargs):
        """Limit to one row."""
        self.pk = "X"
        super().save(*args, **kwargs)
