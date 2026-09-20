"""Bookmark model."""

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db.models import (
    CASCADE,
    BooleanField,
    ForeignKey,
    Index,
    PositiveSmallIntegerField,
    Q,
    UniqueConstraint,
)

from codex.models.base import BaseModel
from codex.models.comic import Comic

__all__ = ("Bookmark", "cascade_if_user_null")


def cascade_if_user_null(
    collector,
    field,
    sub_objs,
    using,  # noqa: ARG001
) -> None:
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
    """Persist user's bookmarks."""

    user = ForeignKey(
        settings.AUTH_USER_MODEL, db_index=True, on_delete=CASCADE, null=True
    )
    session = ForeignKey(
        Session, db_index=True, on_delete=cascade_if_user_null, null=True
    )
    comic = ForeignKey(Comic, db_index=True, on_delete=CASCADE)
    page = PositiveSmallIntegerField(db_index=True, null=True)
    finished = BooleanField(default=False, db_index=True)

    class Meta(BaseModel.Meta):
        """Constraints."""

        # One bookmark per owner per comic. ``unique_together`` on
        # (user, session, comic) could not enforce that: user and session
        # are nullable and SQL treats NULLs in a unique index as
        # distinct, so two rows (user=1, session=NULL, comic=5) both
        # satisfied it. Each constraint is conditioned on its own owner
        # being present, which also binds a row that somehow has both.
        # A row with neither owner falls outside both and belongs to
        # nobody; the nightly cleanup collects those.
        constraints = (
            UniqueConstraint(
                fields=("user", "comic"),
                condition=Q(user__isnull=False),
                name="unique_bookmark_user_comic",
            ),
            UniqueConstraint(
                fields=("session", "comic"),
                condition=Q(session__isnull=False),
                name="unique_bookmark_session_comic",
            ),
        )
        # Comic-leading composites for the per-comic my-bookmark probes
        # (UNREAD/READ filter Exists, bookmark aggregates). Every other
        # index on this table leads with the owner — the partial unique
        # indexes above, and the two FK indexes — and under stale
        # sqlite_stat1 the planner flipped a user-scoped probe onto the
        # plain user index, a measured 17s vs 27ms plan. Comic-first
        # dominates both access paths.
        indexes = (
            Index(fields=("comic", "user"), name="bookmark_comic_user"),
            Index(fields=("comic", "session"), name="bookmark_comic_session"),
        )
