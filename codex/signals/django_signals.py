"""Django signal actions."""

from django.db.models.signals import post_delete, post_save


def _on_library_changed(*_args, **_kwargs) -> None:
    """Clear the libraries_exist cache on Library writes."""
    # Imported lazily so this module stays safe to import before django.setup().
    from codex.views.browser.browser import invalidate_libraries_exist_cache

    invalidate_libraries_exist_cache()


def _on_favorite_target_deleted(sender, instance, **_kwargs) -> None:
    """Drop favorites that pointed at a deleted browsable target."""
    # Lazy imports so the module is safe to load before ``django.setup()``.
    from codex.models.favorite import FAVORITE_MODEL_GROUP_CODES, Favorite

    if group_code := FAVORITE_MODEL_GROUP_CODES.get(sender):
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

    from codex.models import Library
    from codex.models.favorite import FAVORITE_MODEL_GROUP_CODES
    from codex.settings import AUTH_FAILED_LOGIN_LOG

    post_save.connect(_on_library_changed, sender=Library)
    post_delete.connect(_on_library_changed, sender=Library)
    post_save.connect(_ensure_user_auth, sender=get_user_model())

    # Cascade favorites when their target row is deleted. The handler
    # rereads the mapping at fire time so this loop only needs the
    # senders.
    for model in FAVORITE_MODEL_GROUP_CODES:
        post_delete.connect(_on_favorite_target_deleted, sender=model)

    if AUTH_FAILED_LOGIN_LOG:
        from django.contrib.auth.signals import user_login_failed

        from codex.failed_login_log import on_login_failed

        user_login_failed.connect(on_login_failed)

    # User-data sidecar: mirror every user-bound row into a separate
    # SQLite file that survives main-DB rebuilds. Handlers are
    # best-effort and never raise into the request path.
    from codex.user_data.signals import connect_user_data_signals

    connect_user_data_signals()
