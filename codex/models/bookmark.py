"""Bookmeark model."""

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    ForeignKey,
    PositiveSmallIntegerField,
    TextChoices,
)

from codex.models.base import BaseModel
from codex.models.choices import ReadingDirectionChoices, max_choices_len
from codex.models.comic import Comic

__all__ = ("Bookmark", "cascade_if_user_null")


def cascade_if_user_null(
    collector,
    field,
    sub_objs,
    using,  # noqa: ARG001
):
    """
    Cascade only if the user field is null.

    Do this to keep deleting ephemeral session data from Bookmark table.
    Adapted from:
    https://github.com/django/django/blob/master/django/db/models/deletion.py#L23
    """
    # only cascade the ones with null user fields.
    null_user_sub_objs = [sub_obj for sub_obj in sub_objs if sub_obj.user is None]
    if null_user_sub_objs:
        collector.collect(
            null_user_sub_objs,
            source=field.remote_field.model,
            source_attr=field.name,
            nullable=field.null,
        )

    # Set them all to null
    if field.null:
        # and not connections[using].features.can_defer_constraint_checks:
        collector.add_field_update(field, None, sub_objs)


class Bookmark(BaseModel):
    """Persist user's bookmarks and settings."""

    class FitToChoices(TextChoices):
        """Identifiers for Readder fit_to choices."""

        SCREEN = "S"
        WIDTH = "W"
        HEIGHT = "H"
        ORIG = "O"

    user = ForeignKey(
        settings.AUTH_USER_MODEL, db_index=True, on_delete=CASCADE, null=True
    )
    session = ForeignKey(
        Session, db_index=True, on_delete=cascade_if_user_null, null=True
    )
    comic = ForeignKey(Comic, db_index=True, on_delete=CASCADE)
    page = PositiveSmallIntegerField(db_index=True, null=True)
    finished = BooleanField(default=False, db_index=True)
    fit_to = CharField(
        blank=True,
        choices=FitToChoices.choices,
        default="",
        max_length=max_choices_len(FitToChoices),
    )
    two_pages = BooleanField(default=None, null=True)
    reading_direction = CharField(
        blank=True,
        choices=ReadingDirectionChoices.choices,
        default="",
        max_length=max_choices_len(ReadingDirectionChoices),
    )

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("user", "session", "comic")
