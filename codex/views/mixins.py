"""Cross view annotation methods."""

from django.db.models.expressions import F

from codex.models.comic import Comic, Imprint, Volume
from codex.views.const import GROUP_NAME_MAP

_SHOW_GROUPS = tuple(GROUP_NAME_MAP.keys())


class SharedAnnotationsMixin:
    """Cross view annotation methods."""

    @staticmethod
    def _get_order_groups(pks, model_group):
        """Annotate sort_name."""
        if not pks or len(pks) > 1:
            order_groups = _SHOW_GROUPS
        elif model_group == "c":
            order_groups = ()
        else:
            for index, nav_group in enumerate(_SHOW_GROUPS):
                if nav_group == model_group:
                    order_groups = _SHOW_GROUPS[index + 1 :]
                    break
            else:
                order_groups = _SHOW_GROUPS
        return order_groups

    @classmethod
    def alias_sort_names(cls, qs, model, pks, model_group, show=None):
        """Annotate sort names for browser subclasses and reader."""
        sort_name_annotations = {}
        comic_sort_names = []
        if model == Comic:
            order_groups = cls._get_order_groups(pks, model_group)
            for order_group in order_groups:
                if show and not show.get(order_group):
                    continue
                group_name = GROUP_NAME_MAP[order_group]
                ann_name = f"{group_name}_sort_name"
                name_field = "name" if group_name == "volume" else "sort_name"
                sort_name = F(f"{group_name}__{name_field}")
                sort_name_annotations[ann_name] = sort_name
                comic_sort_names.append(ann_name)
        elif model == Volume:
            sort_name_annotations["sort_name"] = F("name")

        if sort_name_annotations:
            qs = qs.alias(**sort_name_annotations)
        return qs, comic_sort_names

    @classmethod
    def annotate_group_names(cls, qs, model):
        """Annotate name fields by hoisting them up."""
        # Optimized to only lookup what is used on the frontend
        target = cls.TARGET  # type: ignore
        if target not in frozenset({"browser", "opds1", "opds2", "reader"}):
            return qs
        group_names = {}
        if model == Comic:
            if target != "reader":
                group_names["publisher_name"] = F("publisher__name")
                if target == "opds2":
                    group_names["imprint_name"] = F("imprint__name")
            group_names.update(
                {
                    "series_name": F("series__name"),
                    "volume_name": F("volume__name"),
                }
            )
        elif model == Volume:
            group_names["series_name"] = F("series__name")
        elif model == Imprint:
            group_names["publisher_name"] = F("publisher__name")
        return qs.annotate(**group_names)
