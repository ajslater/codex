"""View for marking comics read and unread."""

from collections.abc import Iterable
from functools import cached_property
from types import MappingProxyType
from typing import Any, cast, override

from caseconverter import snakecase
from django.db.models import Exists, F, Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.choices.browser import (
    BROWSER_READING_LIST_KIND_CHOICES,
    DUMMY_NULL_NAME,
    VUETIFY_NULL_CODE,
)
from codex.models import (
    Comic,
    CreditPerson,
    ReadingList,
)
from codex.models.age_rating import AgeRating, AgeRatingMetron
from codex.models.identifier import IdentifierSource
from codex.models.named import Reprint, Universe
from codex.serializers.browser.choices import (
    REPRINT_LABEL_FIELDS,
    BrowserChoicesFilterSerializer,
    BrowserFilterChoicesSerializer,
)
from codex.serializers.browser.settings import BrowserFilterChoicesInputSerializer
from codex.views.browser.const import MATCH_ALL_KEY
from codex.views.browser.filters.filter import BrowserFilterView
from codex.views.browser.filters.reading_lists import (
    READING_LIST_KIND_FILTER,
    READING_LISTS_FILTER,
    listed_comics,
    listed_q,
)
from codex.views.readinglists.access import (
    LIST_KINDS,
    list_kind_q,
    list_kinds_for,
    visible_lists,
)
from codex.views.settings import (
    CREDIT_PERSON_UI_FIELD,
    IDENTIFIER_TYPE_UI_FIELD,
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
        IdentifierSource: "identifier__",
    }
)
# Series attributes, reached across the series FK. They aren't Comic fields,
# so ``get_rel_and_model`` can't look them up on the model.
_SERIES_ATTR_FIELD_RELS = MappingProxyType(
    {
        "series_end_year": "series__end_year",
        "series_start_year": "series__start_year",
        "series_status": "series__status",
    }
)
# Plain columns whose "None" is a blank string, never NULL.
_BLANK_IS_NULL_RELS = frozenset({"series__status"})
# Plain fields that offer a "None" choice, so they take the m2m
# availability rule: two distinct values, or a value and a "None".
_NULL_CHOICE_FIELDS = frozenset({"series_status"})
# Plain fields whose choices are serialized as {pk, name} rows.
_NAMED_ROW_CHOICE_FIELDS = frozenset({"community_rating", "file_type", "series_status"})
_NULL_NAMED_ROW = MappingProxyType({"pk": VUETIFY_NULL_CODE, "name": DUMMY_NULL_NAME})
# We only need to know whether an m2m relation has two or more distinct
# non-null values; ``[:2]`` is enough to distinguish 0/1/>=2 cases.
_M2M_DISTINCT_PROBE_LIMIT = 2
# The Reading List Kind is offered when it has two kinds to choose between.
_KINDS_TO_CHOOSE = 2
_KIND_OMITTED = frozenset({READING_LIST_KIND_FILTER})
# The filters about lists: they need a list the user can see.
_LIST_FIELDS = frozenset({READING_LISTS_FILTER, READING_LIST_KIND_FILTER})
# Choice models the menu shows in rating order, by ``index``.
_INDEX_ORDERED_MODELS = frozenset({AgeRating, AgeRatingMetron})


class BrowserChoicesViewBase(BrowserFilterView):
    """Get choices for filter dialog."""

    input_serializer_class = BrowserFilterChoicesInputSerializer
    TARGET: str = "choices"

    @staticmethod
    def present(comic_qs: QuerySet, rel: str) -> QuerySet:
        """Comics with a value for the relation."""
        comic_qs = comic_qs.filter(**{f"{rel}__isnull": False})
        if rel in _BLANK_IS_NULL_RELS:
            comic_qs = comic_qs.exclude(**{rel: ""})
        return comic_qs

    @staticmethod
    def absent(comic_qs: QuerySet, rel: str) -> QuerySet:
        """Comics without a value for the relation, the "None" choice."""
        query = Q(**{f"{rel}__isnull": True})
        if rel in _BLANK_IS_NULL_RELS:
            query |= Q(**{rel: ""})
        return comic_qs.filter(query)

    @classmethod
    def get_field_choices_query(cls, comic_qs, rel):
        """Get distinct values for the field."""
        return cls.present(comic_qs, rel).distinct()

    def get_m2m_field_query(self, model, comic_qs: QuerySet):
        """Get distinct m2m value objects for the relation."""
        back_rel = _BACK_REL_MAP.get(model, "")
        m2m_filter = {f"{back_rel}comic__in": comic_qs}
        return model.objects.filter(**m2m_filter).distinct()

    @classmethod
    def does_null_exist(cls, comic_qs, rel):
        """Get if comics exist in the filter without values for the field."""
        # Detect if there are null choices. Regretably with another query.
        return cls.absent(comic_qs, rel).exists()

    def get_rel_and_model(self, field_name) -> tuple:
        """Return the relation and model for the field name."""
        rel_and_model = _FIELD_TO_REL_MODEL_MAP.get(field_name)
        if rel_and_model:
            rel, model = rel_and_model
        elif rel := _SERIES_ATTR_FIELD_RELS.get(field_name):
            model = None
        else:
            remote_field = getattr(
                Comic._meta.get_field(field_name), "remote_field", None
            )
            rel = field_name
            model = remote_field.model if remote_field else None

        return rel, model

    def reading_lists_of(self, comic_qs: QuerySet) -> QuerySet:
        """Return the visible lists holding any of the comics: own first, by name."""
        return (
            visible_lists(self.request.user)
            .filter(entries__comic__in=comic_qs.values("pk"), entries__ignored=False)
            .distinct()
            .order_by(F("user_id").asc(nulls_last=True), "sort_name", "pk")
        )

    def picked_list_kinds(self) -> frozenset[str]:
        """Return the Reading List Kinds the viewer has picked."""
        filters = self.params.get("filters") or {}
        return frozenset(filters.get(READING_LIST_KIND_FILTER) or ())

    def list_kind_probes(self) -> dict[str, QuerySet]:
        """
        Per kind the viewer may pick, the rows that show it is offered.

        On the grid of lists, the lists of that kind; elsewhere, the comics
        here on a visible list of that kind; inside one list none, as the
        kind does nothing there. Every other filter applies and the kind
        itself is left out, so a picked kind leaves the others offered and
        switching is one step.
        """
        if self.is_in_lists():
            return {}
        user = self.request.user
        kinds = list_kinds_for(user)
        if self.is_lists_grid(ReadingList):
            lists = self.get_filtered_queryset(ReadingList, omit=_KIND_OMITTED)
            return {
                kind: self.force_inner_joins(lists.filter(list_kind_q((kind,), user)))
                for kind in kinds
            }
        comics = self.get_filtered_queryset(Comic, omit=_KIND_OMITTED)
        return {kind: comics.filter(listed_q(user, kinds=(kind,))) for kind in kinds}

    def unlisted(self, comic_qs: QuerySet) -> QuerySet:
        """Return the comics in no list the user may see, the "None" choice."""
        return comic_qs.exclude(pk__in=listed_comics(self.request.user))

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

    @classmethod
    def _has_two_distinct_m2m_values(cls, comic_qs: QuerySet, rel: str) -> bool:
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
            cls.present(comic_qs, rel)
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
        # ``serializer_class`` is typed ``type[BaseSerializer] | None`` on
        # the parent ViewSet but this subclass always sets it.
        serializer_cls = cast(
            "type[BrowserFilterChoicesSerializer]", self.serializer_class
        )
        serializer = serializer_cls()
        for field_name in serializer.get_fields():
            if bool(filters.get(field_name)):
                # Active filter on this dimension — the user is already
                # filtering by it, so it must be available.
                early_data[field_name] = True
                continue
            if field_name in _LIST_FIELDS:
                self._list_field_probes(
                    field_name, qs, early_data, aggregates, m2m_specs
                )
                continue
            rel, m2m_model = self.get_rel_and_model(field_name)
            if m2m_model is None and field_name not in _NULL_CHOICE_FIELDS:
                # FK on Comic: legacy semantic is "any non-null value exists".
                aggregates[field_name] = Exists(self.present(qs, rel).values("pk")[:1])
            else:
                # m2m / m2m-through and plain fields with a "None" choice:
                # legacy semantic is "(distinct rels >= 2)
                # OR (>= 1 rel AND a null sibling)". Decompose into two
                # cheap EXISTS booleans; the rarer "1 rel, 0 null" case
                # falls back to a per-field distinct-count probe below.
                m2m_specs[field_name] = rel
                aggregates[f"_has_{field_name}"] = Exists(
                    self.present(qs, rel).values("pk")[:1]
                )
                aggregates[f"_null_{field_name}"] = Exists(
                    self.absent(qs, rel).values("pk")[:1]
                )
        return early_data, aggregates, m2m_specs

    def _list_field_probes(
        self,
        field_name: str,
        qs: QuerySet,
        early_data: dict[str, bool],
        aggregates: dict[str, Exists],
        m2m_specs: dict[str, str],
    ) -> None:
        """Probe the Reading Lists or the Reading List Kind filter."""
        if not self._sees_lists:
            # No list to be on, and no kind to pick.
            early_data[field_name] = False
        elif field_name == READING_LISTS_FILTER:
            self._reading_lists_probes(qs, aggregates, m2m_specs)
        else:
            for kind, rows in self.list_kind_probes().items():
                aggregates[f"_kind_{kind}"] = Exists(rows.values("pk")[:1])

    @cached_property
    def _sees_lists(self) -> bool:
        """Whether the user sees any list: the list probes need one."""
        return visible_lists(self.request.user).exists()

    def _reading_lists_probes(
        self, qs: QuerySet, aggregates: dict[str, Exists], m2m_specs: dict[str, str]
    ) -> None:
        """Probe the reading lists like an m2m field, over visible lists only."""
        listed = listed_q(self.request.user)
        m2m_specs[READING_LISTS_FILTER] = ""
        aggregates[f"_has_{READING_LISTS_FILTER}"] = Exists(
            qs.filter(listed).values("pk")[:1]
        )
        aggregates[f"_null_{READING_LISTS_FILTER}"] = Exists(
            qs.filter(~listed).values("pk")[:1]
        )

    def _resolve_m2m_field(
        self, qs: QuerySet, field_name: str, rel: str, row: dict[str, Any]
    ) -> bool:
        """Resolve one m2m field from the (has_rel, has_null) booleans."""
        has_rel = bool(row.get(f"_has_{field_name}"))
        if not has_rel:
            return False
        if bool(row.get(f"_null_{field_name}")):
            return True
        if field_name == READING_LISTS_FILTER:
            lists = self.reading_lists_of(qs).values("pk")
            return (
                lists[:_M2M_DISTINCT_PROBE_LIMIT].count() >= _M2M_DISTINCT_PROBE_LIMIT
            )
        return self._has_two_distinct_m2m_values(qs, rel)

    @override
    def get_object(self) -> dict[str, Any]:  # pyright: ignore[reportIncompatibleMethodOverride], # ty: ignore[incompatible-method-override]
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
        if READING_LIST_KIND_FILTER not in data:
            offered = sum(bool(row.get(f"_kind_{kind}")) for kind in LIST_KINDS)
            data[READING_LIST_KIND_FILTER] = offered >= _KINDS_TO_CHOOSE
        return data


class BrowserChoicesView(BrowserChoicesViewBase):
    """
    Get one filter's choices.

    Several values in one filter match any of them, so the filter's own
    value is left out when its choices are built: ticking a character
    never shrinks the characters offered. The other filters still narrow
    them. A ticked value is always listed so it can be unticked, named
    only through what the viewer may see.
    """

    serializer_class: type[BaseSerializer] | None = BrowserChoicesFilterSerializer

    def _ticked(self, field_name: str) -> tuple:
        """Return the values ticked in the field's own filter."""
        filters = self.params.get("filters") or {}
        return tuple(filters.get(field_name) or ())

    @staticmethod
    def _unshown(rows: list[dict], ticked: tuple) -> list:
        """Return the ticked pks not among the rows, None aside."""
        shown = {row["pk"] for row in rows}
        return [
            pk for pk in dict.fromkeys(ticked) if pk is not None and pk not in shown
        ]

    @staticmethod
    def _project_m2m_rows(qs: QuerySet) -> Iterable[dict[str, Any]]:
        """Project a choice model's rows to what its serializer reads."""
        values = ["pk", "name"]
        if qs.model == Reprint:
            # No ``name`` column at all — BrowserChoicesReprintPkSerializer
            # composes the label from these.
            values = ["pk", *REPRINT_LABEL_FIELDS]
        elif qs.model == Universe:
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
        return qs.values(*values)

    def _visible_ticked_rows(self, model, pks: list) -> Iterable[dict[str, Any]]:
        """
        Return the ticked values found on comics the viewer may see.

        Through the ACL filter alone, so a tag on hidden comics only is
        never named. A raw pk lookup would name it.
        """
        back_rel = _BACK_REL_MAP.get(model, "")
        visible = Comic.objects.filter(self.get_acl_filter(Comic, self.request.user))
        rows = model.objects.filter(
            pk__in=pks, **{f"{back_rel}comic__in": visible}
        ).distinct()
        return self._project_m2m_rows(rows)

    def _get_m2m_field_choices(self, model, comic_qs, rel, ticked: tuple):
        """Get choices with nulls where there are nulls, and the ticked."""
        rows = list(self._project_m2m_rows(self.get_m2m_field_query(model, comic_qs)))
        if unshown := self._unshown(rows, ticked):
            rows.extend(self._visible_ticked_rows(model, unshown))
            if model in _INDEX_ORDERED_MODELS:
                # SQLite sorts a NULL index first.
                rows.sort(key=lambda row: (row["index"] is not None, row["index"] or 0))
        if None in ticked or self.does_null_exist(comic_qs, rel):
            return (_NULL_NAMED_ROW, *rows)
        return rows

    def _reading_list_choices(self, qs: QuerySet, ticked: tuple):
        """Return the visible lists over the comics, and "None" if any is unlisted."""
        rows = list(self.reading_lists_of(qs).values("pk", "name"))
        if unshown := self._unshown(rows, ticked):
            lists = visible_lists(self.request.user).filter(pk__in=unshown)
            rows.extend(lists.order_by("sort_name", "pk").values("pk", "name"))
        if None in ticked or self.unlisted(qs).exists():
            return (_NULL_NAMED_ROW, *rows)
        return rows

    def _plain_field_choices(self, field_name: str, qs: QuerySet, rel: str, ticked):
        """Return a plain column's values, the ticked ones echoed."""
        values = list(self.get_field_choices_query(qs, rel).values_list(rel, flat=True))
        shown = set(values)
        values.extend(
            value
            for value in dict.fromkeys(ticked)
            if value is not None and value not in shown
        )
        if field_name not in _NAMED_ROW_CHOICE_FIELDS:
            # A bare value list has no "None" row; the menu drops one.
            return values
        rows = tuple({"pk": value, "name": value} for value in values)
        if None in ticked or (
            field_name in _NULL_CHOICE_FIELDS and self.does_null_exist(qs, rel)
        ):
            return (_NULL_NAMED_ROW, *rows)
        return rows

    def _list_kind_choices(self) -> tuple[dict[str, str], ...]:
        """Return the kinds with lists behind them, and any picked, in order."""
        picked = self.picked_list_kinds()
        probes = self.list_kind_probes()
        return tuple(
            {"pk": kind, "name": BROWSER_READING_LIST_KIND_CHOICES[kind]}
            for kind in LIST_KINDS
            if kind in picked or (kind in probes and probes[kind].exists())
        )

    def _get_field_name(self):
        field_name = self.kwargs.get("field_name", "")
        return snakecase(field_name)

    @override
    def get_object(self) -> dict[str, Any]:  # pyright: ignore[reportIncompatibleMethodOverride], # ty: ignore[incompatible-method-override]
        """
        Return the field's choices, its own filter left out under Any.

        Under All the filter's own ticks stay applied, so its list is what
        still occurs with them. The Age Rating tabs are two fields; each
        leaves out its own key only, so a tick in one still narrows the
        other.
        """
        field_name = self._get_field_name()
        filters = self.params.get("filters") or {}
        omit = () if field_name in (filters.get(MATCH_ALL_KEY) or ()) else (field_name,)
        qs = self.get_filtered_queryset(Comic, omit=omit)
        ticked = self._ticked(field_name)
        if field_name == READING_LISTS_FILTER:
            choices = self._reading_list_choices(qs, ticked)
        elif field_name == READING_LIST_KIND_FILTER:
            choices = self._list_kind_choices()
        else:
            rel, m2m_model = self.get_rel_and_model(field_name)
            if m2m_model:
                choices = self._get_m2m_field_choices(m2m_model, qs, rel, ticked)
            else:
                choices = self._plain_field_choices(field_name, qs, rel, ticked)
        return {"field_name": field_name, "choices": choices}
