"""Django views for Codex."""
import logging

from django.contrib.admin import ModelAdmin, register
from django.contrib.admin.templatetags.admin_urls import admin_urlname
from django.shortcuts import resolve_url
from django.utils.html import format_html

from codex.librarian.cover import purge_all_covers
from codex.librarian.queue import (
    QUEUE,
    LibraryChangedTask,
    RestartTask,
    ScannerCronTask,
    ScanRootTask,
    UpdateCronTask,
    WatcherCronTask,
)
from codex.models import AdminFlag, FailedImport, Library


LOG = logging.getLogger(__name__)


@register(Library)
class AdminLibrary(ModelAdmin):
    """Admin model for Library."""

    fieldsets = (
        (None, {"fields": ("path", "enable_watch")}),
        ("Scans", {"fields": ("last_scan", "scan_in_progress")}),
        ("Scheduled Scans", {"fields": ("enable_scan_cron", "scan_frequency")}),
    )
    actions = ("scan", "force_scan")
    empty_value_display = "Never"
    list_display = (
        "path",
        "enable_watch",
        "enable_scan_cron",
        "scan_frequency",
        "last_scan",
        "scan_in_progress",
    )
    # Django admin will not display datetime fields if they're not editable
    list_editable = (
        "enable_watch",
        "enable_scan_cron",
        "scan_frequency",
        "scan_in_progress",
        # XXX can't submit anything at all if this doesn't have a value.
        #  I mark this disabled and readonly with javascript. Ugly.
        #  This a django bug.
        "last_scan",
    )
    readonly_fields = ("last_scan",)
    sortable_by = list_display

    def _scan(self, request, queryset, force):
        """Queue a scan task for the library."""
        pks = queryset.values_list("pk", flat=True)
        for pk in pks:
            task = ScanRootTask(pk, force)
            QUEUE.put(task)

    def scan(self, request, queryset):
        """Scan for new comics."""
        self._scan(request, queryset, False)

    scan.short_description = "Scan for changes"

    def force_scan(self, request, queryset):
        """Scan all comics."""
        self._scan(request, queryset, True)

    force_scan.short_description = "Re-import all comics"

    def _on_change(self, obj, created=False):
        """Events for when the library has changed."""
        # XXX These sleep values are for waiting for db consistency
        #     between processes. Klugey.
        if created:
            QUEUE.put(LibraryChangedTask())
            QUEUE.put(ScannerCronTask(sleep=1))
        QUEUE.put(WatcherCronTask(sleep=1))

    def save_model(self, request, obj, form, change):
        """Trigger watching and scanning on update or creation."""
        created = obj.pk is None
        super().save_model(request, obj, form, change)
        if change or created:
            self._on_change(obj, created)

    def delete_model(self, request, obj):
        """Stop watching on delete."""
        purge_all_covers(obj)
        super().delete_model(request, obj)
        QUEUE.put(WatcherCronTask(sleep=1))
        QUEUE.put(LibraryChangedTask())

    def delete_queryset(self, request, queryset):
        """Bulk delete."""
        for obj in queryset:
            purge_all_covers(obj)
        super().delete_queryset(request, queryset)
        QUEUE.put(WatcherCronTask(sleep=1))
        QUEUE.put(LibraryChangedTask())

    def save_formset(self, request, form, formset, change):
        """Bulk update."""
        super().save_formset(request, form, formset, change)
        if change:
            for form in formset:
                self._on_change(form.instance)


class AdminNoAddDelete(ModelAdmin):
    """An admin model that can't be added or deleted."""

    def has_add_permission(self, request, obj=None):
        """Can't Add these."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Can't Remove these."""
        return False


@register(AdminFlag)
class AdminAdminFlag(AdminNoAddDelete):
    """Admin model for AdminFlags."""

    fields = ("name", "on")
    readonly_fields = ("name",)
    list_display = fields
    list_editable = ("on",)
    sortable_by = fields
    actions = ("update_now", "restart_now")

    def update_now(self, request, queryset):
        """Trigger an update task immediately."""
        QUEUE.put(UpdateCronTask(sleep=0, force=True))

    update_now.short_description = "Update Codex Now"

    def restart_now(self, request, queryset):
        """Send a restart task immediately."""
        QUEUE.put(RestartTask(sleep=0))

    restart_now.short_description = "Restart Codex Now"

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
        task = LibraryChangedTask()
        QUEUE.put(task)


@register(FailedImport)
class AdminFailedImport(AdminNoAddDelete):
    """Display failed imports."""

    fields = ("path", "reason", "created_at", "updated_at", "library_link")
    list_display = fields
    readonly_fields = fields
    sortable_by = fields

    def has_change_permission(self, request, obj=None):
        """Can't Change these."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Sure can delete them tho."""
        return True

    def library_link(self, item):
        """Render a field for linking to the library change page."""
        url = resolve_url(admin_urlname(Library._meta, "change"), item.library.id)
        return format_html(
            '<a href="{url}">{name}</a>'.format(url=url, name=str(item.library))
        )

    library_link.short_description = "Library"
