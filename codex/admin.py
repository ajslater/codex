"""Django views for Codex."""
from logging import getLogger
from threading import Thread
from time import sleep

from django.contrib.admin import ModelAdmin, register
from django.contrib.admin.templatetags.admin_urls import admin_urlname
from django.db.models import Model
from django.shortcuts import resolve_url
from django.urls import get_script_prefix
from django.utils.html import format_html
from django.utils.safestring import SafeText

from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    BroadcastNotifierTask,
    CleanupDatabaseTask,
    CreateComicCoversLibrariesTask,
    PollLibrariesTask,
    PurgeComicCoversLibrariesTask,
    WatchdogSyncTask,
)
from codex.models import AdminFlag, FailedImport, Library


LOG = getLogger(__name__)
SAFE_CHANGE = SafeText("change")


class QueueJob(Model):
    """Fake Model for AdminQueueJob."""

    class Meta:
        """Don't add this to the schema."""

        db_tablespace = "temp"
        managed = False


class AdminNoAddDelete(ModelAdmin):
    """An admin model that can't be added or deleted."""

    def has_add_permission(self, _, obj=None):
        """Can't Add these."""
        return False

    def has_delete_permission(self, _, obj=None):
        """Can't Remove these."""
        return False


@register(QueueJob)
class AdminQueueJob(AdminNoAddDelete):
    """Fake ModelAdmin to display the queue job page."""

    def has_change_permission(self, request, obj=None):
        """Can't Change these."""
        return False

    def get_queryset(self, request):
        """Don't hit the database at all."""
        return QueueJob.objects.none()

    def changelist_view(self, request, extra_context=None):
        """Add script prefix to context."""
        extra_context = extra_context or {}
        extra_context["script_prefix"] = get_script_prefix()
        return super().changelist_view(request, extra_context=extra_context)


class LibraryChangeThread(Thread):
    """
    Kludgy thread to wait for the database to sync between procs.

    Needed because these tasks fail if they're sent right after creation.
    """

    def run(self):
        """Sleep and then put things on the queue."""
        sleep(2)
        LIBRARIAN_QUEUE.put(BroadcastNotifierTask("LIBRARY_CHANGED"))
        LIBRARIAN_QUEUE.put(WatchdogSyncTask())


@register(Library)
class AdminLibrary(ModelAdmin):
    """Admin model for Library."""

    fieldsets = (
        (None, {"fields": ("path",)}),
        ("Watchdog", {"fields": ("events", "poll", "poll_every", "last_poll")}),
    )
    actions = ("poll", "force_poll", "regen_comic_covers")
    empty_value_display = "Never"
    list_display = (
        "path",
        "events",
        "poll",
        "poll_every",
        "last_poll",
    )
    list_editable = (
        "events",
        "poll",
        "poll_every",
    )
    readonly_fields = ("last_poll",)
    sortable_by = list_display

    @staticmethod
    def queue_poll(queryset, force):
        """Queue a poll task for the library."""
        pks = queryset.values_list("pk", flat=True)
        task = PollLibrariesTask(pks, force)
        LIBRARIAN_QUEUE.put(task)

    def poll(self, request, queryset):
        """Poll for new comics."""
        self.queue_poll(queryset, False)

    poll.short_description = "Poll selected libraries for changes"

    def force_poll(self, request, queryset):
        """Poll all comics."""
        self.queue_poll(queryset, True)

    force_poll.short_description = "Update all comics in selected libraries"

    def regen_comic_covers(self, _, queryset):
        """Regenerate all covers."""
        # TODO remove
        pks = queryset.values_list("pk", flat=True)
        LIBRARIAN_QUEUE.put(CreateComicCoversLibrariesTask(pks))

    regen_comic_covers.short_description = "Recreate comic covers in selected libraries"

    def _on_change(self, _, created=False):
        """Events for when the library has changed."""
        LibraryChangeThread().start()

    def save_model(self, request, obj, form, change):
        """Trigger watching and polling on update or creation."""
        created = obj.pk is None
        super().save_model(request, obj, form, change)
        if change or created:
            self._on_change(obj, created)

    def delete_model(self, request, obj):
        """Stop watching on delete."""
        pks = set([obj.pk])
        LIBRARIAN_QUEUE.put(PurgeComicCoversLibrariesTask(pks))
        super().delete_model(request, obj)
        LIBRARIAN_QUEUE.put(CleanupDatabaseTask())
        self._on_change(None)

    def delete_queryset(self, request, queryset):
        """Bulk delete."""
        pks = set(queryset.values_list("pk", flat=True))
        LIBRARIAN_QUEUE.put(PurgeComicCoversLibrariesTask(pks))
        super().delete_queryset(request, queryset)
        LIBRARIAN_QUEUE.put(CleanupDatabaseTask())
        self._on_change(None)

    def save_formset(self, request, form, formset, change):
        """Bulk update."""
        super().save_formset(request, form, formset, change)
        if change:
            # for form in formset:
            self._on_change(form.instance)


@register(AdminFlag)
class AdminAdminFlag(AdminNoAddDelete):
    """Admin model for AdminFlags."""

    fields = ("name", "on")
    readonly_fields = ("name",)
    list_display = fields
    list_editable = ("on",)
    sortable_by = fields

    def save_model(self, request, obj, form, change):
        """Trigger a change notification because options have changed."""
        created = obj.pk is None
        super().save_model(request, obj, form, change)
        if change or created:
            self._on_change()

    def save_formset(self, request, form, formset, change):
        """Bulk update triggers change."""
        super().save_formset(request, form, formset, change)
        if change:
            self._on_change()

    def _on_change(self):
        """Signal UI that its out of date."""
        # Heavy handed refresh everything, but simple.
        # Folder View could only change the group view and let the ui decide
        # Registration only needs to change the enable flag
        task = BroadcastNotifierTask("LIBRARY_CHANGED")
        LIBRARIAN_QUEUE.put(task)


@register(FailedImport)
class AdminFailedImport(AdminNoAddDelete):
    """Display failed imports."""

    fields = ("path", "name", "created_at", "updated_at", "library_link")
    list_display = fields
    readonly_fields = fields
    sortable_by = fields

    def has_change_permission(self, request, obj=None):
        """Can't Change these."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Sure can delete them, though."""
        return True

    def library_link(self, item):
        """Render a field for linking to the library change page."""
        url = resolve_url(admin_urlname(Library._meta, SAFE_CHANGE), item.library.id)
        return format_html(f'<a href="{url}">{item.library.path}</a>')

    def get_queryset(self, request):
        """Select related."""
        return super().get_queryset(request).select_related("library")

    library_link.short_description = "Library"
