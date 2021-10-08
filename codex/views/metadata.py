"""View for marking comics read and unread."""
import logging

from bidict import bidict
from django.db.models import Aggregate, CharField, Count
from rest_framework.response import Response

from codex.models import Comic
from codex.serializers.metadata import MetadataSerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_metadata_base import BrowserMetadataBase
from codex.views.mixins import UserBookmarkMixin


LOG = logging.getLogger(__name__)


class GroupConcat(Aggregate):
    """sqlite3 GROUP_CONCAT function."""

    # https://stackoverrun.com/vi/q/2730644

    # In Postgres we could use ArrayAgg
    function = "GROUP_CONCAT"
    template = "%(function)s(%(x_distinct)s%(expressions)s%(separator)s)"
    allow_distinct = True

    def __init__(self, expression, distinct=False, separator=None, **extra):
        """Pass special arguments for the template."""
        # use x_distinct so as not to override django super.distinct
        super().__init__(
            expression,
            x_distinct="DISTINCT " if distinct else "",
            distict=distinct,
            separator=', "%s"' % separator if separator else "",
            output_field=CharField(),
            **extra,
        )


class MetadataView(BrowserMetadataBase, UserBookmarkMixin):
    """Comic metadata."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    AGGREGATE_FIELDS = set(
        ("bookmark", "x_cover_path", "finished", "progress", "size", "x_page_count")
    )
    # DO NOT USE BY ITSELF. USE get_comic_value_fields() instead.
    COMIC_VALUE_FIELDS = set(
        (
            "country",
            "created_at",
            "critical_rating",
            "day",
            "description",
            "format",
            "issue",
            "language",
            "maturity_rating",
            "month",
            "notes",
            "path",
            "read_ltr",
            "scan_info",
            "summary",
            "title",
            "updated_at",
            "user_rating",
            "web",
            "year",
        )
    )
    ADMIN_COMIC_VALUE_FIELDS = set(("path",))
    COMIC_RELATED_VALUE_FIELD_MAP = bidict(
        {
            "series__volume_count": "volume_count",
            "volume__issue_count": "issue_count",
        }
    )
    COMIC_RELATED_VALUE_ANNOTATIONS = set(COMIC_RELATED_VALUE_FIELD_MAP.values())
    COMIC_RELATED_VALUE_FIELDS = set(COMIC_RELATED_VALUE_FIELD_MAP.keys())
    COMIC_FK_FIELDS = set(
        (
            "imprint",
            "publisher",
            "series",
            "volume",
        )
    )
    COMIC_M2M_FIELDS = set(
        (
            "characters",
            "genres",
            "locations",
            "series_groups",
            "story_arcs",
            "tags",
            "teams",
        )
    )
    PK_LIST_SUFFIX = "_pk_list"
    COUNT_SUFFIX = "_count"
    COMIC_PK_LIST_KEY = "comic" + PK_LIST_SUFFIX

    def get_comic_value_fields(self):
        """Include the path field for staff."""
        fields = self.COMIC_VALUE_FIELDS
        if self.request.user and self.request.user.is_staff:
            fields |= self.ADMIN_COMIC_VALUE_FIELDS
        return fields

    def get_comic_simple_aggregate_fields(self):
        """Include the path field for staff."""
        comic_value_fields = self.get_comic_value_fields()
        return comic_value_fields | self.COMIC_FK_FIELDS

    def get_aggregates(self, aggregate_filter):
        """Return metadata aggregate data and comic pks."""
        # Create the aggregates like we do for the browser
        group = self.kwargs["group"]
        pk = self.kwargs["pk"]

        model = self.GROUP_MODEL[group]

        obj = model.objects.filter(pk=pk)
        if model != Comic:
            size_func = self.get_aggregate_func("size", model, aggregate_filter)
            obj = obj.annotate(size=size_func)
        obj = self.annotate_cover_path(obj, model, aggregate_filter)
        obj = self.annotate_page_count(obj, aggregate_filter)
        obj = self.annotate_bookmarks(obj)
        obj = self.annotate_progress(obj)

        obj = obj.values(*self.AGGREGATE_FIELDS)

        return obj.first()

    def get_comic_queryset(self, aggregate_filter):
        """Get the comic query for getting the pick set & comic."""
        group = self.kwargs["group"]
        pk = self.kwargs["pk"]
        host_rel = self.GROUP_RELATION[group]
        comic_qs = Comic.objects.filter(**{host_rel: pk}).filter(aggregate_filter)
        return comic_qs

    @classmethod
    def build_pick_set(cls, fields, count_dict, pick_sets, key, field_suffix=""):
        """Build a pick set by checking the count_dict."""
        for field in fields:
            count_field = field + field_suffix + cls.COUNT_SUFFIX
            if count_dict[count_field] != 1:
                continue
            pick_sets[key].add(field)

    def get_pick_sets(self, comic_qs):
        """Determine which fields are common across all comics."""
        agg_comics = (
            comic_qs.all()
            .select_related(*self.COMIC_FK_FIELDS)
            .prefetch_related(*self.COMIC_M2M_FIELDS)
        )

        m2m_annotations = {}
        agg_comics = agg_comics.values("pk")  # group by
        for rel in self.COMIC_M2M_FIELDS:
            ann_name = rel + self.PK_LIST_SUFFIX
            func = GroupConcat(f"{rel}__pk", distinct=True)
            m2m_annotations[ann_name] = func
        agg_comics = agg_comics.annotate(**m2m_annotations)

        agg_dict = {self.COMIC_PK_LIST_KEY: GroupConcat("pk", distinct=True)}

        for rel in self.get_comic_simple_aggregate_fields():
            annotation_name = rel + self.COUNT_SUFFIX
            agg_func = Count(rel, distinct=True)
            agg_dict[annotation_name] = agg_func
        for rel in self.COMIC_RELATED_VALUE_FIELDS:
            rel_safe = self.COMIC_RELATED_VALUE_FIELD_MAP[rel]
            annotation_name = rel_safe + self.COUNT_SUFFIX
            agg_func = Count(rel, distinct=True)
            agg_dict[annotation_name] = agg_func
        for rel in self.COMIC_M2M_FIELDS:
            annotation_name = rel + self.COUNT_SUFFIX
            list_annotation = rel + self.PK_LIST_SUFFIX
            agg_func = Count(list_annotation, distinct=True)
            agg_dict[annotation_name] = agg_func

        count_dict = agg_comics.aggregate(**agg_dict)

        # Build pick sets
        pick_sets = {
            "value": set(),
            "related_value": set(),
            "fk": set(),
            "m2m": set(),
        }
        self.build_pick_set(
            self.get_comic_value_fields(), count_dict, pick_sets, "value"
        )
        self.build_pick_set(
            self.COMIC_RELATED_VALUE_ANNOTATIONS, count_dict, pick_sets, "related_value"
        )
        self.build_pick_set(self.COMIC_FK_FIELDS, count_dict, pick_sets, "fk")
        self.build_pick_set(self.COMIC_M2M_FIELDS, count_dict, pick_sets, "m2m")

        only_pick_set = set()
        for pick_set in pick_sets.values():
            only_pick_set |= pick_set
        pick_sets["only"] = only_pick_set

        annotation_pick_set = set()
        for field in pick_sets["related_value"]:
            annotation = self.COMIC_RELATED_VALUE_FIELD_MAP.inverse[field]
            annotation_pick_set.add(annotation)
        serialize_pick_set = (
            only_pick_set - pick_sets["related_value"] | annotation_pick_set
        )
        pick_sets["serialize"] = serialize_pick_set

        # Parse comic pks
        comic_pks = set()
        pk_list = count_dict[self.COMIC_PK_LIST_KEY].split(",")
        for pk in pk_list:
            if pk:
                comic_pks.add(int(pk))

        return (comic_pks, pick_sets)

    def get_comic(self, aggregate_filter):
        """Get the comic and the final pick set."""
        # The filtered comic query for the pick set & comic
        comic_qs = self.get_comic_queryset(aggregate_filter)

        # Get the pick set from aggregates.
        comic_pks, pick_sets = self.get_pick_sets(comic_qs)

        # add the deep relation roots to the select_related
        select_related = pick_sets["fk"]
        for ann in pick_sets["related_value"]:
            rel = self.COMIC_RELATED_VALUE_FIELD_MAP.inverse[ann]
            rel = rel.split("__")[0]
            select_related.add(rel)

        # Get one comic but only the common fields.
        comic_qs = Comic.objects.select_related(*select_related).prefetch_related(
            *pick_sets["m2m"]
        )

        # Annotate the comic with the related values and adjust
        # the pick set to match.
        for annotation in pick_sets["related_value"]:
            relation = self.COMIC_RELATED_VALUE_FIELD_MAP[annotation]
            comic_qs = comic_qs.annotate(**{annotation: relation})
        comic_qs = comic_qs.only(*pick_sets["only"])

        # Just get one comic
        _first_comic_pk = None
        for _first_comic_pk in comic_pks:
            break
        comic = comic_qs.get(pk=_first_comic_pk)

        return comic, comic_pks, pick_sets["serialize"]

    def get(self, request, *args, **kwargs):
        """Get metadata for a single comic."""
        # Init
        self.params = self.get_session(self.BROWSER_KEY)
        aggregate_filter = self.get_aggregate_filter()

        # The aggregates that share code with browser
        aggregates = self.get_aggregates(aggregate_filter)

        # Get the comic & final pick set for the serializer
        comic, comic_pks, comic_fields = self.get_comic(aggregate_filter)

        data = {"pks": list(comic_pks), "aggregates": aggregates, "comic": comic}
        serializer = MetadataSerializer(data, comic_fields=comic_fields)

        return Response(serializer.data)
