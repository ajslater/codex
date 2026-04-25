"""View for marking comics read and unread."""

from itertools import chain
from types import MappingProxyType
from typing import Any, override

from caseconverter import snakecase
from django.db.models import Exists, F, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.choices.browser import DUMMY_NULL_NAME, VUETIFY_NULL_CODE
from codex.models import (
    Comic,
    CreditPerson,
    StoryArc,
)
from codex.models.age_rating import AgeRating, AgeRatingMetron
from codex.models.identifier import IdentifierSource
from codex.models.named import Universe
from codex.serializers.browser.choices import (
    BrowserChoicesFilterSerializer,
    BrowserFilterChoicesSerializer,
)
from codex.serializers.browser.settings import BrowserFilterChoicesInputSerializer
from codex.views.browser.filters.filter import BrowserFilterView
from codex.views.settings import (
    CREDIT_PERSON_UI_FIELD,
    IDENTIFIER_TYPE_UI_FIELD,
    STORY_ARC_UI_FIELD,
)

_AGE_RATING_TAGGED_FIELD = "age_rating_tagged"
_AGE_RATING_METRON_FIELD = "age_rating_metron"

_FIELD_TO_REL_MODEL_MAP = MappingProxyType(
    {
        _AGE_RATING_TAGGED_FIELD: (
            "age_rating",
            AgeRating,
        ),
        _AGE_RATING_METRON_FIELD: (
            "age_rating__metron",
            AgeRatingMetron,
        ),
        CREDIT_PERSON_UI_FIELD: (
            "credits__person",
            CreditPerson,
        ),
        IDENTIFIER_TYPE_UI_FIELD: (
            "identifiers__source",
            IdentifierSource,
        ),
        STORY_ARC_UI_FIELD: (
            "story_arc_numbers__story_arc",
            StoryArc,
        ),
    }
)
# Reverse-query prefixes from the choice model back to Comic. Used to build
# filter kwargs like ``{back_rel}comic__in=comic_qs``. Models with a direct
# FK reverse (AgeRating.comic_set from Comic.age_rating, Character, …) omit
# the prefix and take the empty-string default.
_BACK_REL_MAP = MappingProxyType(
    {
        # AgeRatingMetron traverses AgeRating to reach Comic:
        # AgeRatingMetron -> agerating -> comic
        AgeRatingMetron: "agerating__",
        CreditPerson: "credit__",
        StoryArc: "storyarcnumber__",
        IdentifierSource: "identifier__",
    }
)
_NULL_NAMED_ROW = MappingProxyType({"pk": VUETIFY_NULL_CODE, "name": DUMMY_NULL_NAME})
_NULL_NAMED_ROW_ITERABLE = (_NULL_NAMED_ROW,)
# We only need to know whether an m2m relation has two or more distinct
# non-null values; ``[:2]`` is enough to distinguish 0/1/>=2 cases.
_M2M_DISTINCT_PROBE_LIMIT = 2


class BrowserChoicesViewBase(BrowserFilterView):
    """Get choices for filter dialog."""

    input_serializer_class: type[BrowserFilterChoicesInputSerializer] = (  # pyright: ignore[reportIncompatibleVariableOverride]
        BrowserFilterChoicesInputSerializer
    )
    TARGET: str = "choices"

    @staticmethod
    def get_field_choices_query(comic_qs, field_name):
        """Get distinct values for the field."""
        return comic_qs.exclude(**{f"{field_name}__isnull": True}).distinct()

    def get_m2m_field_query(self, model, comic_qs: QuerySet):
        """Get distinct m2m value objects for the relation."""
        back_rel = _BACK_REL_MAP.get(model, "")
        m2m_filter = {f"{back_rel}comic__in": comic_qs}
        return model.objects.filter(**m2m_filter).distinct()

    @staticmethod
    def does_m2m_null_exist(comic_qs, rel):
        """Get if comics exist in the filter without values exists for an m2m field."""
        # Detect if there are null choices. Regretably with another query.
        return comic_qs.filter(**{f"{rel}__isnull": True}).exists()

    def get_rel_and_model(self, field_name) -> tuple:
        """Return the relation and model for the field name."""
        rel_and_model = _FIELD_TO_REL_MODEL_MAP.get(field_name)
        if rel_and_model:
            rel, model = rel_and_model
        else:
            remote_field = getattr(
                Comic._meta.get_field(field_name), "remote_field", None
            )
            rel = field_name
            model = remote_field.model if remote_field else None

        return rel, model

    @override
    def get_object(self) -> QuerySet:
        """Get the comic subquery use for the choices."""
        return self.get_filtered_queryset(Comic)

    @extend_schema(parameters=[input_serializer_class])
    def get(self, *_args, **_kwargs) -> Response:
        """Return choices."""
        obj = self.get_object()
        serializer = self.get_serializer(obj)
        return Response(serializer.data)


class BrowserChoicesAvailableView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    serializer_class: type[BaseSerializer] | None = BrowserFilterChoicesSerializer

    @staticmethod
    def _has_two_distinct_m2m_values(comic_qs: QuerySet, rel: str) -> bool:
        """
        Return True iff ``rel`` resolves to >= 2 distinct non-null values.

        The natural ``EXISTS(SELECT DISTINCT rel ... LIMIT 1 OFFSET 1)`` form
        is broken on SQLite: ``EXISTS`` short-circuits on the first row from
        the underlying join, before ``DISTINCT`` collapses or ``OFFSET``
        skips. Materializing the first two distinct values via Python and
        checking length sidesteps the bug while still capping work at two
        rows scanned.
        """
        first_two = list(
            comic_qs.filter(**{f"{rel}__isnull": False})
            .values_list(rel, flat=True)
            .distinct()[:_M2M_DISTINCT_PROBE_LIMIT]
        )
        return len(first_two) >= _M2M_DISTINCT_PROBE_LIMIT

    def _build_field_probes(
        self, qs: QuerySet
    ) -> tuple[dict[str, bool], dict[str, Exists], dict[str, str]]:
        """
        Walk the dynamic filter fields and partition them into probe groups.

        Returns ``(early_data, aggregates, m2m_specs)``:

        * ``early_data`` — fields whose availability is decided without SQL
          (story-arc browse skip, active filter shortcuts).
        * ``aggregates`` — kwargs for the batched ``EXISTS`` annotate call.
          FK fields use their public ``field_name``; m2m fields contribute
          ``_has_<name>`` and ``_null_<name>`` underscored keys.
        * ``m2m_specs`` — ``field_name -> rel`` for fields that need the
          post-aggregate resolve step.
        """
        filters = self.params.get("filters") or {}
        early_data: dict[str, bool] = {}
        aggregates: dict[str, Exists] = {}
        m2m_specs: dict[str, str] = {}
        serializer: BrowserFilterChoicesSerializer = self.serializer_class()  # pyright: ignore[reportOptionalCall, reportAssignmentType], # ty: ignore[call-non-callable, invalid-assignment]
        for field_name in serializer.get_fields():
            if field_name == "story_arcs" and qs.model is StoryArc:
                # don't allow filtering on story arc in story arc view.
                continue
            if bool(filters.get(field_name)):
                # Active filter on this dimension — the user is already
                # filtering by it, so it must be available.
                early_data[field_name] = True
                continue
            rel, m2m_model = self.get_rel_and_model(field_name)
            if m2m_model is None:
                # FK on Comic: legacy semantic is "any non-null value exists".
                aggregates[field_name] = Exists(
                    qs.filter(**{f"{field_name}__isnull": False}).values("pk")[:1]
                )
            else:
                # m2m / m2m-through: legacy semantic is "(distinct rels >= 2)
                # OR (>= 1 rel AND a null sibling)". Decompose into two
                # cheap EXISTS booleans; the rarer "1 rel, 0 null" case
                # falls back to a per-field distinct-count probe below.
                m2m_specs[field_name] = rel
                aggregates[f"_has_{field_name}"] = Exists(
                    qs.filter(**{f"{rel}__isnull": False}).values("pk")[:1]
                )
                aggregates[f"_null_{field_name}"] = Exists(
                    qs.filter(**{f"{rel}__isnull": True}).values("pk")[:1]
                )
        return early_data, aggregates, m2m_specs

    def _resolve_m2m_field(
        self, qs: QuerySet, field_name: str, rel: str, row: dict[str, Any]
    ) -> bool:
        """Resolve one m2m field from the (has_rel, has_null) booleans."""
        has_rel = bool(row.get(f"_has_{field_name}"))
        if not has_rel:
            return False
        if bool(row.get(f"_null_{field_name}")):
            return True
        return self._has_two_distinct_m2m_values(qs, rel)

    @override
    def get_object(self) -> dict[str, Any]:  # pyright: ignore[reportIncompatibleMethodOverride], # ty: ignore[invalid-method-override]
        """Get choice availability for all dynamic filter fields in one query."""
        qs = super().get_object()
        data, aggregates, m2m_specs = self._build_field_probes(qs)
        if aggregates:
            # One SQL round-trip: pin a 1-row anchor on Comic and let SQLite
            # evaluate every EXISTS subquery in one shot. The anchor row's
            # pk is irrelevant — only the subqueries' booleans matter, and
            # the EXISTS clauses are uncorrelated to the outer row.
            row = (
                qs.model.objects.values("pk")
                .annotate(**aggregates)
                .values(*aggregates.keys())
                .first()
            ) or {}
        else:
            row = {}

        # FK fields drop straight in by their public name.
        data.update(
            {
                name: bool(row.get(name))
                for name in aggregates
                if not name.startswith("_")
            }
        )
        # m2m fields fan out from the (has_rel, has_null) booleans, with a
        # distinct-count probe only for the (has_rel, ¬has_null) corner.
        for field_name, rel in m2m_specs.items():
            data[field_name] = self._resolve_m2m_field(qs, field_name, rel, row)
        return data


class BrowserChoicesView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    serializer_class: type[BaseSerializer] | None = BrowserChoicesFilterSerializer

    def _get_m2m_field_choices(self, model, comic_qs, rel):
        """Get choices with nulls where there are nulls."""
        iterables = []

        # Choices
        qs = self.get_m2m_field_query(model, comic_qs)
        values = ["pk", "name"]
        if qs.model == Universe:
            values.append("designation")
        elif qs.model == AgeRatingMetron:
            # AgeRatingMetron.Meta.ordering = ("index",), but ``.distinct()``
            # with ``.values("pk", "name")`` drops it because ``index`` isn't
            # in the SELECT projection. Include it and sort explicitly so the
            # UI shows ratings in rating order rather than alphabetical.
            values.append("index")
            qs = qs.order_by("index")
        elif qs.model == AgeRating:
            values.extend(["index", "metron_name"])
            qs = qs.annotate(
                index=F("metron__index"), metron_name=F("metron__name")
            ).order_by("index")
        qs = qs.values(*values)

        # Add null if it exists
        if self.does_m2m_null_exist(comic_qs, rel):
            iterables.append(_NULL_NAMED_ROW_ITERABLE)

        iterables.append(qs)

        return chain.from_iterable(iterables)

    def _get_field_name(self):
        field_name = self.kwargs.get("field_name", "")
        return snakecase(field_name)

    @override
    def get_object(self) -> dict[str, Any]:  # pyright: ignore[reportIncompatibleMethodOverride], # ty: ignore[invalid-method-override]
        """Return choices with more than one choice."""
        qs = super().get_object()
        field_name = self._get_field_name()

        rel, m2m_model = self.get_rel_and_model(field_name)

        if m2m_model:
            choices = self._get_m2m_field_choices(m2m_model, qs, rel)
        else:
            choices = self.get_field_choices_query(qs, field_name)
            choices = choices.values_list(field_name, flat=True)

        if field_name in ("critical_rating", "file_type"):
            choices = tuple({"pk": choice, "name": choice} for choice in choices)

        return {
            "field_name": field_name,
            "choices": choices,
        }
