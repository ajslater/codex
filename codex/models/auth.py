"""Admin Auth models."""

from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models import (
    CASCADE,
    SET_NULL,
    BooleanField,
    ForeignKey,
    OneToOneField,
)

from codex.models.age_rating import AgeRatingMetron
from codex.models.base import BaseModel

__all__ = ("GroupAuth", "UserAuth")


class UserAuth(BaseModel):
    """
    Per-user auth attributes + last-active timestamp.

    Successor to the former ``UserActive`` model. Carries both the
    activity timestamp (via :attr:`~codex.models.base.BaseModel.updated_at`)
    and the per-user age-rating ceiling.

    :attr:`age_rating_metron` is nullable. NULL ⇒ unrestricted: the user can
    see every comic regardless of rating. A concrete FK pins the user's
    ceiling at the referenced row's :attr:`AgeRatingMetron.index`.
    """

    user = OneToOneField(settings.AUTH_USER_MODEL, db_index=True, on_delete=CASCADE)
    age_rating_metron = ForeignKey(
        AgeRatingMetron,
        db_index=True,
        null=True,
        blank=True,
        default=None,
        on_delete=SET_NULL,
    )


class GroupAuth(BaseModel):
    """Extended Attributes for Groups."""

    group = OneToOneField(Group, db_index=True, on_delete=CASCADE)
    exclude = BooleanField(db_index=True, default=False)
