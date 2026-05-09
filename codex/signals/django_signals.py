"""Django signal actions."""

from django.db.models.signals import post_delete, post_save

# Populated by :func:`connect_signals` once Django apps are loaded.
# Maps each browseable target model to its ``Favorite.group`` letter
# code so the post-delete handler can drop matching rows without
# re-deriving the mapping on every fire.
_FAVORITE_TARGET_GROUP_CODES: dict[type, str] = {}


def _on_library_changed(*_args, **_kwargs) -> None:
    """Clear the libraries_exist cache on Library writes."""
    # Imported lazily so this module stays safe to import before django.setup().
    from codex.views.browser.browser import invalidate_libraries_exist_cache

    invalidate_libraries_exist_cache()


def _on_favorite_target_deleted(sender, instance, **_kwargs) -> None:
    """Drop favorites that pointed at a deleted browseable target."""
    from codex.models.favorite import Favorite

    if group_code := _FAVORITE_TARGET_GROUP_CODES.get(sender):
        Favorite.objects.filter(group=group_code, target_id=instance.pk).delete()


def _ensure_user_auth(sender, instance, created, **_kwargs) -> None:
    """
    Provision a :class:`UserAuth` row alongside every newly-created User.

    Centralises the invariant "every User has a UserAuth" so all
    creation paths satisfy it: ``manage.py createsuperuser``, the
    admin web UI's ``perform_create``, fixtures, factory_boy, ad-hoc
    shell sessions. Previously only the admin UI created the row,
    leaving ``createsuperuser``-provisioned admins without one — and
    triggering "No UserAuth row for user pk=N" warnings from the
    bookmark thread on every activity touch.

    ``get_or_create`` keeps the handler idempotent: a duplicate
    ``post_save`` (e.g. fixture loaders that re-save) won't IntegrityError
    on the OneToOne unique constraint.
    """
    del sender
    if not created:
        return
    from codex.models.auth import UserAuth

    UserAuth.objects.get_or_create(user=instance)


def connect_signals() -> None:
    """Connect actions to signals."""
    # Imported lazily for the same reason as above.
    from django.contrib.auth import get_user_model

    from codex.models import (
        Comic,
        Folder,
        Imprint,
        Library,
        Publisher,
        Series,
        StoryArc,
        Volume,
    )

    post_save.connect(_on_library_changed, sender=Library)
    post_delete.connect(_on_library_changed, sender=Library)
    post_save.connect(_ensure_user_auth, sender=get_user_model())

    # Cascade favorites when their target row is deleted. Mirrors the
    # group-letter codes from `FAVORITE_GROUP_CHOICES`.
    _FAVORITE_TARGET_GROUP_CODES.update(
        {
            Publisher: "p",
            Imprint: "i",
            Series: "s",
            Volume: "v",
            Folder: "f",
            StoryArc: "a",
            Comic: "c",
        }
    )
    for model in _FAVORITE_TARGET_GROUP_CODES:
        post_delete.connect(_on_favorite_target_deleted, sender=model)
