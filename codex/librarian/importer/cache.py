"""Update Groups timestamp for cover cache busting."""

import os

from django.db.models.aggregates import Count
from django.db.models.functions.datetime import Now
from django.db.models.query import Q

from codex.librarian.importer.init import InitImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Comic, Folder, Imprint, Publisher, Series, StoryArc, Volume
from codex.status import Status

_FIRST_COVER_MODEL_UPDATE_ORDER = (Volume, Series, Imprint, Publisher, Folder, StoryArc)
_UPDATE_FIELDS = ("first_comic", "updated_at")


class CacheUpdateImporter(InitImporter):
    """Update Groups timestamp for cover cache busting."""

    @staticmethod
    def _get_folder_batches(model_qs):
        """Create batches of folders by folder depth level."""
        # Collect all related folders
        folder_pks = model_qs.values_list("pk", flat=True)
        all_folders = (
            Folder.objects.filter(Q(folder__pk__in=folder_pks) | Q(pk__in=folder_pks))
            .select_related("first_comic")
            .only("path", *_UPDATE_FIELDS)
        )

        # Create a map of each folder by path depth level
        batch_map = {}
        for folder in all_folders:
            depth = folder.path.count(os.sep)
            if depth not in batch_map:
                batch_map[depth] = set()
            batch_map[depth].add(folder)

        # Order batches by reverse depth level to update bottom up.
        batches = []
        for _, folders in sorted(batch_map.items(), reverse=True):
            batches.append(folders)

        return tuple(batches)

    @staticmethod
    def _update_first_cover_volume(obj):
        qs = Comic.objects.filter(volume=obj)
        qs = qs.order_by("issue_number", "issue_suffix", "sort_name").only("pk")
        obj.first_comic = qs.first()

    @staticmethod
    def _update_first_cover_group(obj, model, field):
        qs = model.objects.filter(**{field: obj})
        order_by = "name" if model == Volume else "sort_name"
        qs = qs.select_related("first_comic").order_by(order_by).only("first_comic")
        obj.first_comic = qs.first().first_comic

    @staticmethod
    def _update_first_cover_story_arc(obj):
        qs = Comic.objects.filter(story_arc_numbers__story_arc=obj)
        qs = qs.order_by("story_arc_numbers__number", "date").only("pk")
        obj.first_comic = qs.first()

    @staticmethod
    def _update_first_cover_folder(obj):
        first_comic = (
            Comic.objects.filter(parent_folder=obj)
            .order_by("path")
            .only("path")
            .first()
        )
        first_folder = (
            Folder.objects.filter(parent_folder=obj)
            .select_related("first_comic")
            .order_by("path")
            .only("first_comic", "path")
            .first()
        )
        if first_comic and not first_folder:
            obj.first_comic = first_comic
        elif first_folder and not first_comic:
            obj.first_comic = first_folder.first_comic
        elif first_folder and first_comic:
            if first_comic and first_comic.path < first_folder.path:
                obj.first_comic = first_comic
            else:
                obj.first_comic = first_folder.first_comic

    @classmethod
    def _update_first_cover(cls, model, obj):
        if model == Volume:
            cls._update_first_cover_volume(obj)
        elif model == Series:
            cls._update_first_cover_group(obj, Volume, "series")
        elif model == Imprint:
            cls._update_first_cover_group(obj, Series, "imprint")
        elif model == Publisher:
            cls._update_first_cover_group(obj, Imprint, "publisher")
        elif model == StoryArc:
            cls._update_first_cover_story_arc(obj)
        elif model == Folder:
            cls._update_first_cover_folder(obj)

    @classmethod
    def _update_group_first_comic(
        cls, force_update_group_map, model, start_time, log_list
    ):
        rel = "storyarcnumber__" if model == StoryArc else ""
        updated_at_rel = rel + "comic__updated_at__gt"
        updated_filter = {updated_at_rel: start_time}
        filter_query = (
            Q(**updated_filter)
            | Q(first_comic__isnull=True)
            | Q(updated_at__gt=start_time)
        )
        if model != Volume:
            filter_query |= Q(custom_cover__updated_at__gt=start_time)
        pks = force_update_group_map.get(model)
        if pks:
            filter_query |= Q(pk__in=pks)
        model_qs = model.objects.filter(filter_query)

        # only update those with comics
        rel_prefix = "storyarcnumber__" if model == StoryArc else ""
        rel_prefix += "comic"
        model_qs = model_qs.alias(child_count=Count(f"{rel_prefix}__pk", distinct=True))
        model_qs = model_qs.filter(child_count__gt=0)
        model_qs = model_qs.distinct()
        if model == Folder:
            batches = cls._get_folder_batches(model_qs)
        else:
            model_qs.select_related("first_comic").only(*_UPDATE_FIELDS)
            batches = (model_qs,)

        total_count = 0
        for model_qs in batches:
            updated = []
            for obj in model_qs:
                cls._update_first_cover(model, obj)
                obj.updated_at = Now()
                updated.append(obj)

            count = len(updated)
            if count:
                model.objects.bulk_update(updated, _UPDATE_FIELDS)
                total_count += count
        if total_count:
            log_list.append(f"{total_count} {model.__name__}s")
        return total_count

    def update_all_groups_first_comics(self, force_update_group_map, start_time):
        """Update timestamps for each group for cover cache busting."""
        total_count = 0
        status = Status(ImportStatusTypes.GROUP_UPDATE)
        self.status_controller.start(status)
        try:
            log_list = []
            for model in _FIRST_COVER_MODEL_UPDATE_ORDER:
                # self.log.debug(f"Updating first covers for {model.__name__}s...")
                count = self._update_group_first_comic(
                    force_update_group_map, model, start_time, log_list
                )
                if count:
                    self.log.debug(
                        f"Updated {count} first covers for {model.__name__}s"
                    )
                status.add_complete(count)
                self.status_controller.update(status, notify=False)
                total_count += count

            if total_count:
                groups_log = ", ".join(log_list)
                self.log.info(  # type: ignore
                    f"Updated first covers for {groups_log}."
                )
                self.changed += total_count
        finally:
            self.status_controller.finish(status)
