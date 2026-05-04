"""Publication Methods for OPDS v2.0 feed."""

import json
from collections.abc import Mapping, Sequence
from types import MappingProxyType, SimpleNamespace
from typing import Any, override

from django.db.models import CharField, F, Value

from codex.models.base import NamedModel
from codex.models.groups import Volume
from codex.models.identifier import Identifier
from codex.models.named import Credit, StoryArcNumber
from codex.serializers.opds.v2.publication import (
    OPDS2PublicationDivinaManifestSerializer,
)
from codex.views.auth import GroupACLMixin
from codex.views.opds.const import (
    AUTHOR_ROLES,
    BLANK_TITLE,
    OPDS_M2M_MODELS,
    MimeType,
    Rel,
)
from codex.views.opds.v2.const import HrefData, LinkData
from codex.views.opds.v2.feed.publications import OPDS2PublicationBaseView

_MD_CREDIT_MAP = MappingProxyType(
    # If OPDS2 is ever popular, make this comprehensive by using comicbox role enums
    {
        "author": AUTHOR_ROLES,
        "translator": {"Translator"},
        "editor": {"Editor"},
        "artist": {"CoverArtist", "Cover", "Artist"},
        "illustrator": {"Illustrator"},
        "letterer": {"Letterer"},
        "penciller": {"Penciller"},
        "colorist": {"Colorist", "Colors"},
        "inker": {"Inker", "Inks"},
        "contributor": {"Contributor"},
        "narrator": {"Narrator"},
    }
)
_PUBLICATION_FIELD_MAP: MappingProxyType[str, str] = MappingProxyType(
    {
        "description": "summary",
    }
)
# Readium Contributor browse-group routing for publisher/imprint —
# matches the helper in ``codex/views/opds/v2/feed/publications.py``.
_CONTRIBUTOR_KINDS: tuple[str, ...] = ("publisher", "imprint")

_PUBLICATION_METHOD_KEYS: tuple[str, ...] = (
    "identifier",
    "belongs_to",
    "subject",
)
# Out-of-range page sentinel used to resolve the ``opds:bin:page`` URL
# template once and format-substitute per iteration in
# ``_publication_reading_order``. Any positive int wider than realistic
# page counts works; 999999999 is well clear of any plausible
# ``page_count`` (sub-plan 05 #4).
_READING_ORDER_PAGE_SENTINEL: int = 999999999


class OPDS2ManifestMetadataView(OPDS2PublicationBaseView):
    """Publication Manifest Divina Extended Metadata."""

    def _publication_identifier(self, obj) -> str:
        rel = GroupACLMixin.get_rel_prefix(Identifier)
        comic_filter = {rel + "in": [obj.pk]}
        identifiers = (
            Identifier.objects.filter(**comic_filter)
            .annotate(source_name=F("source__name"))
            .only("id_type", "key")
            .order_by("source_name", "key")
        )
        return ",".join(
            f"{identifier.source_name}:{identifier.id_type}:{identifier.key}"  # pyright: ignore[reportAttributeAccessIssue]
            for identifier in identifiers
        )

    def _publication_belongs_to_link(
        self,
        kwargs: Mapping[str, str | int | Sequence[int]],
        query_params: Mapping[str, str | int | Mapping],
        name: str,
        number: int | None,
    ) -> list[dict]:
        href_data = HrefData(
            kwargs,
            query_params,
            url_name="opds:v2:feed",
        )
        link_data = LinkData(Rel.SUB, href_data, mime_type=MimeType.OPDS_JSON)
        link = self.link(link_data)
        belongs_to: dict[str, str | list | int] = {"name": name, "links": [link]}
        if number:
            belongs_to["position"] = number
        return [belongs_to]

    def _publication_belongs_to_series(self, obj):
        name = obj.series_name if obj.series.name else BLANK_TITLE
        pks: list[int] = [obj.series.pk]
        kwargs: Mapping[str, str | Sequence[int] | int] = {
            "group": "s",
            "pks": pks,
            "page": 1,
        }
        number = obj.issue_number
        ts = self._obj_ts(obj)
        query_params = {
            "ts": ts,
            "topGroup": "p",
        }

        return self._publication_belongs_to_link(kwargs, query_params, name, number)

    def _publication_belongs_to_volume(self, obj) -> list:
        volume_name = obj.volume_name
        if volume_name is None:
            return []
        display_name = Volume.to_str(volume_name, obj.volume_number_to) or BLANK_TITLE
        kwargs = {"group": "v", "pks": [obj.volume_id], "page": 1}
        ts = self._obj_ts(obj)
        query_params = {"ts": ts, "topGroup": "p"}
        return self._publication_belongs_to_link(
            kwargs, query_params, display_name, volume_name
        )

    def _publication_belongs_to_folder(self, obj) -> list:
        if not self.is_allowed(obj):
            return []
        folder = obj.parent_folder
        name = folder.path
        pks = [folder.pk]
        kwargs = {"group": "f", "pks": pks, "page": 1}
        number = None
        ts = self._obj_ts(obj)
        query_params = {"ts": ts, "topGroup": "f"}

        return self._publication_belongs_to_link(kwargs, query_params, name, number)

    def _publication_belongs_to_story_arcs(self, obj) -> list:
        story_arcs = []
        rel = GroupACLMixin.get_rel_prefix(StoryArcNumber)
        comic_filter = {rel + "in": [obj.pk]}
        # ``select_related("story_arc")`` materializes the FK in the
        # same query — the prior ``.only("story_arc", "number")`` form
        # deferred the FK and triggered a per-row ``StoryArc.objects.get``
        # (textbook N+1, sub-plan 05 #2).
        story_arc_numbers = (
            StoryArcNumber.objects.filter(**comic_filter)
            .select_related("story_arc")
            .only("number", "story_arc__name")
            .order_by("story_arc__name")
        )
        ts = self._obj_ts(obj)
        for story_arc_number in story_arc_numbers:
            story_arc = story_arc_number.story_arc
            name = story_arc.name or BLANK_TITLE
            pks = [story_arc.pk]
            number = story_arc_number.number
            kwargs = {"group": "a", "pks": pks, "page": 1}
            query_params = {"ts": ts, "topGroup": "a"}

            story_arc = self._publication_belongs_to_link(
                kwargs, query_params, name, number
            )
            story_arcs += story_arc
        return story_arcs

    def _publication_belongs_to(self, obj) -> dict:
        belongs_to = {}
        if series := self._publication_belongs_to_series(obj):
            belongs_to["series"] = series
        if volume := self._publication_belongs_to_volume(obj):
            belongs_to["volume"] = volume
        if folder := self._publication_belongs_to_folder(obj):
            belongs_to["collection"] = folder
        if story_arcs := self._publication_belongs_to_story_arcs(obj):
            belongs_to["story_arc"] = story_arcs

        return belongs_to

    def _add_tag_link(self, obj: Any, filter_key: str, subfield: str = "") -> None:
        # ``obj`` can be either a real ``NamedModel`` (when called with
        # ``subfield=""``) or a ``SimpleNamespace`` carrying ``pk`` /
        # ``name`` / ``links`` (the partitioned ``_publication_subject``
        # rows). Typing as ``Any`` lets both shapes through; the
        # function only reads ``pk`` / ``name`` and writes ``links``.
        kwargs = {"group": "s", "pks": (), "page": 1}
        value = getattr(obj, subfield) if subfield else obj
        filters = {filter_key: [value.pk]}
        filters = json.dumps(filters)
        query_params = {
            "topGroup": "s",
            "filters": filters,
            "title": value.name,
        }
        href_data = HrefData(kwargs, query_params, url_name="opds:v2:feed")
        link_data = LinkData(
            Rel.FACET,
            href_data,
            mime_type=MimeType.OPDS_JSON,
        )
        link = self.link(link_data)
        obj.links = (link,)

    def _publication_subject(self, obj) -> tuple[NamedModel, ...]:
        """
        Fetch all M2M subject rows in one UNION query, partition by kind.

        Replaces the prior 7-query loop in ``get_m2m_objects`` (one query
        per ``OPDS_M2M_MODELS`` entry) with a single ``UNION ALL`` over
        ``(pk, name, _kind)`` tuples (sub-plan 05 #3). The reconstructed
        ``SimpleNamespace`` rows expose only ``pk`` / ``name`` / ``links``
        — the surface ``_add_tag_link`` and ``OPDS2SubjectSerializer``
        actually read.
        """
        if not OPDS_M2M_MODELS:
            return ()
        queries = []
        for model in OPDS_M2M_MODELS:
            rel = GroupACLMixin.get_rel_prefix(model)
            kind = model.__name__.lower()
            q = (
                model.objects.filter(**{rel + "in": obj.ids})
                .annotate(_kind=Value(kind, output_field=CharField()))
                .values("pk", "name", "_kind")
            )
            queries.append(q)
        rows = queries[0].union(*queries[1:], all=True).order_by("_kind", "name")

        # ``flat_subjs`` carries ``SimpleNamespace`` rows that quack
        # like ``NamedModel`` (``pk`` / ``name`` / ``links``); the
        # serializer downstream reads only those three attributes.
        flat_subjs: list[Any] = []
        for row in rows:
            kind = row["_kind"]
            subj = SimpleNamespace(pk=row["pk"], name=row["name"], links=())
            self._add_tag_link(subj, kind + "s")
            flat_subjs.append(subj)
        return tuple(flat_subjs)

    def _publication_credits(self, obj) -> Mapping[str, tuple[Credit, ...]]:
        """
        Fetch all credits for the comic in one query, partition by role.

        Replaces the prior 11-query loop (one ``get_credits`` filter per
        ``_MD_CREDIT_MAP`` key) plus the lazy ``credit.person`` FK fan-out
        triggered by ``_add_tag_link``. ``select_related("person", "role")``
        materializes both joins in the same query (sub-plan 05 #1).
        """
        all_credits = list(
            Credit.objects.filter(comic__in=obj.ids)
            .select_related("person", "role")
            .annotate(name=F("person__name"), role_name=F("role__name"))
        )
        if not all_credits:
            return {}

        by_role: dict[str, list[Credit]] = {}
        for credit in all_credits:
            by_role.setdefault(credit.role_name, []).append(credit)  # pyright: ignore[reportAttributeAccessIssue]

        credit_md: dict[str, tuple[Credit, ...]] = {}
        for key, roles in _MD_CREDIT_MAP.items():
            bucket = [c for role in roles for c in by_role.get(role, [])]
            if not bucket:
                continue
            for credit in bucket:
                self._add_tag_link(credit, "credits", "person")
            credit_md[key] = tuple(bucket)
        return credit_md

    def _publication_contributors(self, obj) -> dict:
        """Return the populated publisher/imprint Contributor map for ``obj``."""
        contributors = {}
        for kind in _CONTRIBUTOR_KINDS:
            if contributor := self._publication_contributor(obj, kind):
                contributors[kind] = contributor
        return contributors

    @override
    def _publication_metadata(self, obj, zero_pad) -> dict:
        md = super()._publication_metadata(obj, zero_pad)

        # Direct attribute to key mappings
        for md_key, attr in _PUBLICATION_FIELD_MAP.items():
            if value := getattr(obj, attr, None):
                md[md_key] = value

        # Publisher/imprint render as Contributor objects (name + browse link).
        md.update(self._publication_contributors(obj))

        # Special cases with transforms
        if lang := obj.language:
            md["language"] = lang.name
        if layout := obj.reading_direction:
            md["layout"] = "scrolled" if layout == "ttb" else layout

        # Method-based keys
        for key in _PUBLICATION_METHOD_KEYS:
            if value := getattr(self, f"_publication_{key}")(obj):
                md[key] = value

        if credit_md := self._publication_credits(obj):
            md.update(credit_md)
        return md


class OPDS2ManifestView(OPDS2ManifestMetadataView):
    """Single publication manifest view."""

    serializer_class = OPDS2PublicationDivinaManifestSerializer

    def _publication_reading_order(self, obj) -> list:
        """
        Reader manifest for OPDS 2.0.

        This part of the spec is redundant, but required. Resolves the
        ``opds:bin:page`` URL once with a sentinel page index, then
        format-substitutes the actual page number per iteration —
        eliminates ``N - 1`` ``reverse()`` calls per manifest hit (sub-plan
        05 #4). For a 500-page PDF that's 499 reverse() calls saved.
        """
        if not obj or not obj.page_count:
            return []
        ts = self._obj_ts(obj)
        query_params = {"ts": ts}
        # Use a sentinel index outside the natural range; widen the
        # ``max_page`` validation bound so ``self.href`` accepts it.
        sentinel = _READING_ORDER_PAGE_SENTINEL
        sentinel_href_data = HrefData(
            {"pk": obj.pk, "page": sentinel},
            query_params,
            url_name="opds:bin:page",
            min_page=0,
            max_page=sentinel,
        )
        template_href = self.href(sentinel_href_data)
        if template_href is None:
            return []
        # ``opds:bin:page`` resolves to ``.../<pk>/<page>/page.jpg`` so
        # the sentinel appears as ``/<sentinel>/`` in the path. Replacing
        # that single segment yields a Python format template.
        template = template_href.replace(f"/{sentinel}/", "/{page}/")
        # ``type`` is required by the spec but not calculated for
        # efficiency; height/width aren't required by Stump or other
        # known clients so they're omitted.
        return [
            {"href": template.format(page=page_num), "type": MimeType.JPEG}
            for page_num in range(obj.page_count)
        ]

    def _cover(self, obj) -> list:
        images = []
        if not obj:
            return images
        ts = self._obj_ts(obj)
        pk = obj.ids[0]
        kwargs = {"pk": pk, "page": 0}
        query_params = {"ts": ts, "bookmark": False, "pixmap": True}

        image_href_data = HrefData(
            kwargs,
            query_params,
            url_name="opds:bin:page",
            min_page=0,
        )
        image_link_data = LinkData(
            Rel.IMAGE,
            image_href_data,
            mime_type=MimeType.JPEG,
            # Include dummy heights just to pass client validation
            height=0,
            width=0,
            authenticate=self.auth_link,
        )
        image_link = self.link(image_link_data)
        images.append(image_link)
        return images

    @override
    def _publication(self, obj, zero_pad) -> dict:
        pub = super()._publication(obj, zero_pad)
        # DiViNa manifest uses resources instead of images
        if resources := self._cover(obj):
            pub["resources"] = resources
        if reading_order := self._publication_reading_order(obj):
            pub["reading_order"] = reading_order
        return pub

    @override
    def get_object(self) -> MappingProxyType:
        """Get one publication object."""
        book_qs, _, zero_pad = self.get_book_qs()
        # ``_publication_belongs_to_folder`` reads ``obj.parent_folder.path``
        # when folder_view is enabled. Without this join, every manifest
        # hit on a folder-gated install fires one lazy ``Folder.get`` per
        # request (sub-plan 05 #8). Adding the join here keeps the cost
        # scoped to the manifest path — feeds don't need it.
        book_qs = book_qs.select_related("parent_folder")
        obj = book_qs.first()
        return MappingProxyType(self._publication(obj, zero_pad))
