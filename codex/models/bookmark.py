"""Bookmeark model."""

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    Choices,
    ForeignKey,
    PositiveSmallIntegerField,
)

from codex.models.base import BaseModel, max_choices_len
from codex.models.comic import Comic, ReadingDirection

__all__ = ("Bookmark", "cascade_if_user_null")


def cascade_if_user_null(
    collector,
    field,
    sub_objs,
    using,  # noqa: ARG001
):
    """Cascade only if the user field is null.

    Do this to keep deleting ephemeral session data from Bookmark table.
    Adapted from:
    https://github.com/django/django/blob/master/django/db/models/deletion.py#L23
    """
    null_user_sub_objs = []
    for sub_obj in sub_objs:
        # only cascade the ones with null user fields.
        if sub_obj.user is None:
            null_user_sub_objs.append(sub_obj)

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

    class FitTo(Choices):
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
        choices=FitTo.choices,
        default="",
        max_length=max_choices_len(FitTo),
    )
    two_pages = BooleanField(default=None, null=True)
    reading_direction = CharField(
        blank=True,
        choices=ReadingDirection.choices,
        default="",
        max_length=max_choices_len(ReadingDirection),
    )

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("user", "session", "comic")
