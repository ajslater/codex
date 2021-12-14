"""View for marking comics read and unread."""
from copy import copy
from logging import getLogger

from django.contrib.auth.models import User
from django.db.models import CharField, F, Value
from rest_framework.response import Response

from codex.models import Comic
from codex.serializers.metadata import MetadataSerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser_metadata_base import BrowserMetadataBase
from codex.views.mixins import UserBookmarkMixin


LOG = getLogger(__name__)


class MetadataView(BrowserMetadataBase, UserBookmarkMixin):
    """Comic metadata."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    # DO NOT USE BY ITSELF. USE get_comic_value_fields() instead.
    COMIC_VALUE_FIELDS = set(
        (
            "country",
            "critical_rating",
            "day",
            "description",
            "format",
            "issue",
            "language",
            "maturity_rating",
            "month",
            "notes",
            "read_ltr",
            "scan_info",
            "summary",
            "user_rating",
            "web",
            "year",
        )
    )
    ADMIN_COMIC_VALUE_FIELDS = set(("path",))
    COMIC_VALUE_FIELDS_CONFLICTING = set(
        (
            "name",
            "updated_at",
            "created_at",
        )
    )
    COMIC_VALUE_FIELDS_CONFLICTING_PREFIX = "conflict_"
    COMIC_FK_FIELDS = set(
        (
            "publisher",
            "imprint",
            "series",
            "volume",
        )
    )
    COMIC_FK_FIELDS_MAP = {
        "f": COMIC_FK_FIELDS,
        "p": COMIC_FK_FIELDS - set(["publisher"]),
        "i": COMIC_FK_FIELDS - set(["imprint"]),
        "s": COMIC_FK_FIELDS - set(["series"]),
        "v": COMIC_FK_FIELDS - set(["volume"]),
        "c": COMIC_FK_FIELDS,
    }
    COMIC_FK_ANNOTATION_PREFIX = "fk_"
    COMIC_RELATED_VALUE_FIELDS = set(("series__volume_count", "volume__issue_count"))
    COUNT_FIELD_MAP = {
        "imprint": ("volume_count", "fk_series_volume_count"),
        "series": ("issue_count", "fk_volume_issue_count"),
    }
    COMIC_M2M_FIELDS = set(
        (
            "characters",
            "credits",
            "genres",
            "locations",
            "series_groups",
            "story_arcs",
            "tags",
            "teams",
        )
    )
    PATH_GROUPS = ("c", "f")

    def get_is_admin(self):
        """Is the current user an admin."""
        user = self.request.user
        return user and isinstance(user, User) and user.is_staff

    def get_comic_value_fields(self):
        """Include the path field for staff."""
        fields = copy(self.COMIC_VALUE_FIELDS)
        is_not_path_group = self.group not in self.PATH_GROUPS
        if self.is_admin and is_not_path_group:
            fields |= self.ADMIN_COMIC_VALUE_FIELDS
        return fields

    def _intersection_annotate(
        self,
        simple_qs,
        qs,
        fields,
        related_suffix="",
        annotation_prefix="",
    ):
        """Annotate the intersection of value and fk fields."""
        for field in fields:
            if self.is_model_comic:
                comic_rel_field = field
            else:
                comic_rel_field = f"comic__{field}"

            # Annotate groups and counts
            csq = simple_qs.values(comic_rel_field).distinct()
            count = csq.count()
            ann_field = (annotation_prefix + field).replace("__", "_")
            if count == 1:
                lookup = F(f"{comic_rel_field}{related_suffix}")
            else:
                # None charfield works for all types
                lookup = Value(None, CharField())

            # SPEED It might be faster if I could drop the csq query into
            #  the annotation as a subquery with a Case When, but I
            #  can't figure out how to to get the count to work in a
            #  subquery.
            qs = qs.annotate(**{ann_field: lookup})
        return qs

    @classmethod
    def _field_copy_fk_count(cls, field_name, obj, val):
        """Copy those pesky fk count fields from annotations."""
        op_field_names = cls.COUNT_FIELD_MAP.get(field_name)
        if not op_field_names:
            return
        count_field, count_src_field_name = op_field_names
        val[count_field] = obj[count_src_field_name]

    @classmethod
    def _field_copy(cls, obj, fields, prefix, fk_field=None):
        """Copy annotation fields into comic type fields."""
        for field_name in fields:
            src_field_name = f"{prefix}{field_name}"
            val = obj[src_field_name]
            if fk_field:
                val = {fk_field: val}
                # Add special count fields
                cls._field_copy_fk_count(field_name, obj, val)
            obj[field_name] = val

    def annotate_aggregates(self, qs):
        """Annotate aggregate values."""
        if not self.is_model_comic:
            size_func = self.get_aggregate_func("size", self.is_model_comic)
            qs = qs.annotate(size=size_func)
        qs = self.annotate_common_aggregates(qs, self.model)
        return qs

    def annotate_values_and_fks(self, qs, simple_qs):
        """Annotate comic values and comic foreign key values."""
        # Simple Values
        if not self.is_model_comic:
            comic_value_fields = self.get_comic_value_fields()
            qs = self._intersection_annotate(simple_qs, qs, comic_value_fields)

            # Conflicting Simple Values
            qs = self._intersection_annotate(
                simple_qs,
                qs,
                self.COMIC_VALUE_FIELDS_CONFLICTING,
                annotation_prefix=self.COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
            )

        # Foreign Keys
        fk_fields = copy(self.COMIC_FK_FIELDS_MAP[self.group])
        qs = self._intersection_annotate(
            simple_qs,
            qs,
            fk_fields,
            related_suffix="__name",
            annotation_prefix=self.COMIC_FK_ANNOTATION_PREFIX,
        )

        # Foreign Keys with special count values
        qs = self._intersection_annotate(
            simple_qs,
            qs,
            self.COMIC_RELATED_VALUE_FIELDS,
            annotation_prefix=self.COMIC_FK_ANNOTATION_PREFIX,
        )
        return qs

    def query_m2m_intersections(self, simple_qs):
        """Query the through models to figure out m2m intersections."""
        # Speed ok, but still does a query per m2m model
        # SPEED Could annotate count all the tags and only select those that
        # have num_child counts
        m2m_intersections = {}
        if self.is_model_comic:
            pk_field = "pk"
        else:
            pk_field = "comic__pk"
        comic_pks = simple_qs.values_list(pk_field, flat=True)
        for field_name in self.COMIC_M2M_FIELDS:
            ThroughModel = getattr(Comic, field_name).through  # noqa: N806
            rel_table_name = field_name[:-1].replace("_", "")
            column_id = rel_table_name + "_id"
            if field_name == "credits":
                role_column_name = rel_table_name + "__role__name"
                person_column_name = rel_table_name + "__person__name"
                table = ThroughModel.objects.filter(comic_id__in=comic_pks).values_list(
                    "comic_id", column_id, role_column_name, person_column_name
                )
            else:
                column_name = rel_table_name + "__name"
                table = ThroughModel.objects.filter(comic_id__in=comic_pks).values_list(
                    "comic_id", column_id, column_name
                )
            pk_sets = {}
            for row in table:
                comic_id = row[0]
                if field_name == "credits":
                    field_id = row[1:4]
                else:
                    field_id = row[1:3]
                if comic_id not in pk_sets:
                    pk_sets[comic_id] = set()
                pk_sets[comic_id].add(field_id)
            if not pk_sets:
                continue
            m2m_intersections[field_name] = set.intersection(*pk_sets.values())
        return m2m_intersections

    def copy_annotations_into_comic_fields(self, obj, m2m_intersections):
        """Copy a bunch of values that i couldn't fit cleanly in the main queryset."""
        if self.model is None:
            raise ValueError(f"Cannot get metadata for {self.group=}")
        group_field = self.model.__name__.lower()
        obj[group_field] = {"name": obj["name"]}
        comic_fk_fields = copy(self.COMIC_FK_FIELDS_MAP[self.group])
        self._field_copy(
            obj,
            comic_fk_fields,
            self.COMIC_FK_ANNOTATION_PREFIX,
            "name",
        )

        if not self.is_model_comic:
            # this must come after fk_fields copy because of name
            # for fk models
            self._field_copy(
                obj,
                self.COMIC_VALUE_FIELDS_CONFLICTING,
                self.COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
            )

        for field_name, values in m2m_intersections.items():
            m2m_dicts = []
            if field_name == "credits":
                for pk, role, person in values:
                    m2m_dicts += [
                        {"pk": pk, "role": {"name": role}, "person": {"name": person}}
                    ]
            else:
                for pk, name in values:
                    m2m_dicts += [{"pk": pk, "name": name}]
            obj[field_name] = m2m_dicts

        # Don't expose the filesystem
        obj["folders"] = None
        obj["parent_folder"] = None
        if not self.is_admin:
            obj["path"] = None
        return obj

    def get_metadata_object(self):
        """Create a comic-like object from the current browser group."""
        # Comic model goes through the same code path as groups because
        # values dicts don't copy relations to the serializer. The values
        # dict is necessary because of the folders view union in browser.py.
        aggregate_filter = self.get_aggregate_filter(self.is_model_comic)
        pk = self.kwargs["pk"]
        if self.model is None:
            raise ValueError(f"Cannot get metadata for {self.group=}")
        qs = self.model.objects.filter(pk=pk).filter(aggregate_filter)

        qs = self.annotate_aggregates(qs)
        simple_qs = qs

        qs = self.annotate_values_and_fks(qs, simple_qs)
        m2m_intersections = self.query_m2m_intersections(simple_qs)
        obj = qs.values()[0]
        obj = self.copy_annotations_into_comic_fields(obj, m2m_intersections)
        return obj

    def get(self, _request, *args, **kwargs):
        """Get metadata for a filtered browse group."""
        # Init
        self.params = self.get_session(self.BROWSER_KEY)
        self.is_admin = self.get_is_admin()
        self.group = self.kwargs["group"]
        self.model = self.GROUP_MODEL[self.group]
        if self.model is None:
            raise ValueError(f"Cannot get metadata for {self.group=}")
        self.is_model_comic = self.group == "c"

        obj = self.get_metadata_object()

        serializer = MetadataSerializer(obj)
        return Response(serializer.data)
