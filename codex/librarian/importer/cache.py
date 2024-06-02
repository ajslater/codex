"""Update Groups timestamp for cover cache busting."""

from django.db.models.functions import Now
from django.db.models.query import Q

from codex.librarian.importer.init import InitImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Comic, Folder, Imprint, Publisher, Series, StoryArc, Volume
from codex.status import Status

_FIRST_COVER_MODEL_UPDATE_ORDER = (Volume, Series, Imprint, Publisher, Folder, StoryArc)
_UPDATE_FIELDS = ("first_comic", "updated_at")


class CacheUpdateImporter(InitImporter):
    """Update Groups timestamp for cover cache busting."""

    def _update_first_cover_volume(self, obj):
        qs = Comic.objects.filter(volume=obj)
        qs = qs.order_by("issue_number", "issue_suffix", "sort_name")
        obj.first_comic = qs.first()

    def _update_first_cover_group(self, obj, model, field):
        qs = model.objects.filter(**{field: obj})
        order_by = "name" if model == Volume else "sort_name"
        qs = qs.order_by(order_by)
        obj.first_comic = qs.first().first_comic

    def _update_first_cover_story_arc(self, obj):
        qs = Comic.objects.filter(story_arc_numbers__story_arc=obj)
        qs = qs.order_by("story_arc_numbers__number", "date")
        obj.first_comic = qs.first()

    def _update_first_cover_folder(self, obj):
        first_comic = Comic.objects.filter(parent_folder=obj).order_by("path").first()
        first_folder = Folder.objects.filter(parent_folder=obj).order_by("path").first()
        if first_comic and not first_folder:
            obj.first_comic = first_comic
        elif first_folder and not first_comic:
            obj.first_comic = first_folder.first_comic
        elif first_folder and first_comic:
            if first_comic and first_comic.path < first_folder.path:
                obj.first_comic = first_comic
            else:
                obj.first_comic = first_folder.first_comic

    def _update_first_cover(self, model, obj):
        if model == Volume:
            self._update_first_cover_volume(obj)
        elif model == Series:
            self._update_first_cover_group(obj, Volume, "series")
        elif model == Imprint:
            self._update_first_cover_group(obj, Series, "imprint")
        elif model == Publisher:
            self._update_first_cover_group(obj, Imprint, "publisher")
        elif model == StoryArc:
            self._update_first_cover_story_arc(obj)
        elif model == Folder:
            self._update_first_cover_folder(obj)

    def update_groups_with_changed_comics(self, deleted_comic_groups):
        """Update timestamps for each group for cover cache busting."""
        total_count = 0
        now = Now()
        status = Status(ImportStatusTypes.GROUP_UPDATE)
        self.status_controller.start(status)
        try:
            log_list = []
            for model in _FIRST_COVER_MODEL_UPDATE_ORDER:
                pks = deleted_comic_groups.get(model)
                rel = "storyarcnumber__" if model == StoryArc else ""
                updated_at_rel = rel + "comic__updated_at__gt"
                updated_filter = {updated_at_rel: self.start_time}
                model_qs = (
                    model.objects.filter(Q(**updated_filter) | Q(pk__in=pks))
                    .distinct()
                    .only(*_UPDATE_FIELDS)
                )
                if model == Folder:
                    # update deepest paths first for first comic aggregation
                    model_qs.order_by("-path")

                updated = []
                for obj in model_qs:
                    self._update_first_cover(model, obj)
                    obj.updated_at = now
                    updated.append(obj)

                count = len(updated)
                if count:
                    model.objects.bulk_update(updated, _UPDATE_FIELDS)
                    log_list.append(f"{count} {model.__name__}s.")
                    total_count += count

                status.add_complete(count)
                self.status_controller.update(status, notify=False)

            if total_count:
                groups_log = ", ".join(log_list)
                self.log.debug(  # type: ignore
                    f"Updated {groups_log} timestamps for browser cache busting."
                )
                self.log.info(  # type: ignore
                    f"Updated {total_count} group timestamps for browser cache busting."
                )
                self.changed += total_count
        finally:
            self.status_controller.finish(status)
