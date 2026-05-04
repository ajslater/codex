"""Django signal actions."""

from django.db.models.signals import post_delete, post_save


def _on_library_changed(*_args, **_kwargs) -> None:
    """Clear the libraries_exist cache on Library writes."""
    # Imported lazily so this module stays safe to import before django.setup().
    from codex.views.browser.browser import invalidate_libraries_exist_cache

    invalidate_libraries_exist_cache()


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

    from codex.models import Library

    post_save.connect(_on_library_changed, sender=Library)
    post_delete.connect(_on_library_changed, sender=Library)
    post_save.connect(_ensure_user_auth, sender=get_user_model())
