"""Django views for Codex."""
from pathlib import Path

from django.contrib.admin import ModelAdmin, register
from django.contrib.admin.checks import ModelAdminChecks
from django.contrib.admin.sites import site
from django.contrib.admin.templatetags.admin_urls import admin_urlname
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.db.models import Model
from django.shortcuts import resolve_url
from django.utils.html import format_html
from django.utils.safestring import SafeText

from codex.librarian.queue_mp import LIBRARIAN_QUEUE, DelayedTasks
from codex.librarian.watchdog.tasks import WatchdogPollLibrariesTask, WatchdogSyncTask
from codex.models import AdminFlag, FailedImport, Folder, Library
from codex.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.settings.logging import get_logger
from codex.settings.patch import patch_registration_setting


LOG = get_logger(__name__)
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


@register(Library)
class AdminLibrary(ModelAdmin):
    """Admin model for Library."""

    class M2MModelAdminChecks(ModelAdminChecks):
        """
        Short circuit the no m2m check.

        Optimized get_queryset prevents this from being a problem.
        """

        def _check_list_display_item(self, obj, item, label):
            if item == "groups":
                return []
            return super()._check_list_display_item(obj, item, label)  # type: ignore

    checks_class = M2MModelAdminChecks

    fieldsets = (
        (None, {"fields": ("path",)}),
        ("Watchdog", {"fields": ("events", "poll", "poll_every", "last_poll")}),
        ("Auth", {"fields": ("groups",)}),
    )
    actions = ("poll", "force_poll", "remove_comic_covers")
    empty_value_display = "Never"
    list_display = (
        "path",
        "events",
        "poll",
        "poll_every",
        "last_poll",
        "groups",
    )
    list_editable = (
        "events",
        "poll",
        "poll_every",
        "groups",
    )
    autocomplete_fields = ("groups",)
    readonly_fields = ("last_poll",)
    sortable_by = list_display
    ordering = ("path", "pk")

    def get_queryset(self, request):
        """Prefetch groups."""
        return super().get_queryset(request).prefetch_related("groups")

    @staticmethod
    def queue_poll(queryset, force):
        """Queue a poll task for the library."""
        pks = queryset.values_list("pk", flat=True)
        task = WatchdogPollLibrariesTask(pks, force)
        LIBRARIAN_QUEUE.put(task)

    def poll(self, request, queryset):
        """Poll for new comics."""
        self.queue_poll(queryset, False)

    poll.short_description = "Poll selected libraries for changes"

    def force_poll(self, request, queryset):
        """Poll all comics."""
        self.queue_poll(queryset, True)

    force_poll.short_description = "Update all comics in selected libraries"

    def _on_change(self, _, created=False):
        """Events for when the library has changed."""
        cache.clear()
        tasks = (LIBRARY_CHANGED_TASK, WatchdogSyncTask())
        task = DelayedTasks(2, tasks)
        LIBRARIAN_QUEUE.put(task)

    def save_model(self, request, obj: Library, form, change):
        """Trigger watching and polling on update or creation."""
        created = obj.pk is None
        super().save_model(request, obj, form, change)
        if change or created:
            if created:
                library = Library.objects.get(path=obj.path)
                folder = Folder(
                    library=library, path=library.path, name=Path(library.path).name
                )
                folder.save()
            self._on_change(obj, created)

    def delete_model(self, request, obj):
        """Stop watching on delete."""
        super().delete_model(request, obj)
        cache.clear()
        self._on_change(None)

    def delete_queryset(self, request, queryset):
        """Bulk delete."""
        for library in queryset:
            # so deletes will cascade
            library.delete()
        cache.clear()
        self._on_change(None)

    def save_formset(self, request, form, formset, change):
        """Bulk update."""
        super().save_formset(request, form, formset, change)
        if change:
            # for form in formset:
            self._on_change(form.instance)

    def get_deleted_objects(self, objs, request):
        """Prevent related objects from displaying on confirmation page due to OOM."""
        to_delete = objs
        model_count = {objs[0].__class__._meta.verbose_name_plural: len(objs)}
        perms_needed = set()
        protected = []
        return to_delete, model_count, perms_needed, protected


@register(AdminFlag)
class AdminAdminFlag(AdminNoAddDelete):
    """Admin model for AdminFlags."""

    fields = ("name", "on")
    readonly_fields = ("name",)
    list_display = fields
    list_editable = ("on",)
    sortable_by = fields
    ordering = ("name", "pk")

    def save_model(self, request, obj: AdminFlag, form, change):
        """Trigger a change notification because options have changed."""
        created = obj.pk is None
        super().save_model(request, obj, form, change)
        if change or created:
            self._on_change(set([obj.name]))

    def save_formset(self, request, form, formset, change):
        """Bulk update triggers change."""
        super().save_formset(request, form, formset, change)
        names = set()
        for fform in formset:
            names.add(fform.cleaned_data.get("name"))
        if change:
            self._on_change(names)

    def _on_change(self, names):
        """Signal UI that its out of date."""
        if AdminFlag.ENABLE_REGISTRATION in names:
            patch_registration_setting()
        # Heavy handed refresh everything, but simple.
        # Folder View could only change the group view and let the ui decide
        # Registration only needs to change the enable flag
        LIBRARIAN_QUEUE.put(LIBRARY_CHANGED_TASK)


@register(FailedImport)
class AdminFailedImport(AdminNoAddDelete):
    """Display failed imports."""

    fields = ("path", "name", "created_at", "updated_at", "library_link")
    list_display = fields
    readonly_fields = fields
    sortable_by = fields
    actions = ("poll",)
    ordering = ("path", "library", "pk")

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

    library_link.short_description = "Library"

    def get_queryset(self, request):
        """Select related."""
        return super().get_queryset(request).select_related("library")

    def poll(self, request, queryset):
        """Poll for new comics."""
        pks = queryset.values_list("library__pk", flat=True)
        task = WatchdogPollLibrariesTask(frozenset(pks), False)
        LIBRARIAN_QUEUE.put(task)

    poll.short_description = "Poll selected failed imports' libraries for changes"


site.unregister(Group)
site.unregister(User)


@register(Group)
class CodexGroupAdmin(GroupAdmin):
    """Remove user_permissions to avoid confusion."""

    fields = ("name",)
    ordering = ("name", "pk")


@register(User)
class CodexUserAdmin(UserAdmin):
    """Remove user_permissions to avoid confusion."""

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (
            ("Permissions"),
            {
                "fields": ("is_active", "is_staff", "is_superuser", "groups"),
            },
        ),
        (("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    filter_horizontal = ("groups",)
    ordering = ("username", "pk")
