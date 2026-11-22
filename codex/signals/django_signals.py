"""Django signal actions."""

from django.db.models.signals import post_delete, post_save

from codex.librarian.mp_queue import LIBRARIAN_QUEUE


def _on_library_changed(*_args, **_kwargs) -> None:
    """Clear the libraries_exist cache on Library writes."""
    # Imported lazily so this module stays safe to import before django.setup().
    from codex.views.browser.browser import invalidate_libraries_exist_cache

    invalidate_libraries_exist_cache()


def _on_shelf_target_deleted(sender, instance, **_kwargs) -> None:
    """Drop shelf items that pointed at a deleted browsable target."""
    # Lazy imports so the module is safe to load before ``django.setup()``.
    from codex.models.shelf import SHELF_MODEL_COLLECTIONS, ShelfItem

    if collection_code := SHELF_MODEL_COLLECTIONS.get(sender):
        ShelfItem.objects.filter(
            collection=collection_code.value, target_id=instance.pk
        ).delete()


def _on_reading_list_deleted(sender, instance, **_kwargs) -> None:
    """Ask the librarian to sync the lists that held a deleted list."""
    del sender
    from codex.librarian.scribe.readinglists.live import COLLECTION_KIND
    from codex.librarian.scribe.readinglists.tasks import ReadingListLiveSyncTask
    from codex.models.readinglist import ReadingListSource

    holders = tuple(
        ReadingListSource.objects.filter(
            kind=COLLECTION_KIND, collection="arcs", target_id=instance.pk
        )
        .values_list("reading_list_id", flat=True)
        .distinct()
        .order_by("reading_list_id")
    )
    if holders:
        LIBRARIAN_QUEUE.put(ReadingListLiveSyncTask(list_pks=holders))
    _forget_list_in_filters(instance.pk)


def _forget_list_in_filters(list_pk: int) -> None:
    """
    Drop a deleted list from every stored Reading Lists filter.

    Covers the live browser and OPDS settings and every saved view, so none
    is left filtering on a list that no longer exists, which matches nothing.
    """
    from codex.models.settings import SettingsBrowserFilters

    for filters in SettingsBrowserFilters.objects.exclude(reading_lists=[]):
        kept = [pk for pk in filters.reading_lists if pk != list_pk]
        if kept != filters.reading_lists:
            filters.reading_lists = kept
            filters.save(update_fields=("reading_lists", "updated_at"))


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

    from codex.models import Library, ReadingList
    from codex.models.shelf import SHELF_MODEL_COLLECTIONS
    from codex.settings import AUTH_FAILED_LOGIN_LOG

    post_save.connect(_on_library_changed, sender=Library)
    post_delete.connect(_on_library_changed, sender=Library)
    post_save.connect(_ensure_user_auth, sender=get_user_model())
    post_delete.connect(_on_reading_list_deleted, sender=ReadingList)

    from django.contrib.auth.signals import user_logged_in

    from codex.signals.login import adopt_session_rows

    user_logged_in.connect(adopt_session_rows)

    # Cascade shelf items when their target row is deleted. The handler
    # rereads the mapping at fire time so this loop only needs the
    # senders.
    for model in SHELF_MODEL_COLLECTIONS:
        post_delete.connect(_on_shelf_target_deleted, sender=model)

    if AUTH_FAILED_LOGIN_LOG:
        from django.contrib.auth.signals import user_login_failed

        from codex.failed_login_log import on_login_failed

        user_login_failed.connect(on_login_failed)
