"""Publication Methods for OPDS v2.0 feed."""

import json
from collections.abc import Mapping, Sequence
from types import MappingProxyType, SimpleNamespace
from typing import Any, override

from django.db.models import CharField, F, Min, Value
from rest_framework.exceptions import NotFound

from codex.models.base import NamedModel
from codex.models.collections import Volume
from codex.models.comic import Comic
from codex.models.identifier import Identifier
from codex.models.named import Credit, StoryArc
from codex.models.readinglist import (
    ReadingListEntry,
    ReadingListSource,
    ReadingListSourceKind,
)
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
from codex.views.opds.v2.renderers import OPDS2ManifestRenderer

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


_STORY_ARC_KIND = StoryArc.__name__.lower()
# Each subject kind's browser filter key.
_SUBJECT_FILTER_KEYS = MappingProxyType(
    {
        "character": "characters",
        "genre": "genres",
        "location": "locations",
        "seriesgroup": "series_groups",
        _STORY_ARC_KIND: "reading_lists",
        "tag": "tags",
        "team": "teams",
    }
)


def _arc_list_pks(arc_pks) -> dict[int, int]:
    """Map story arcs to the reading lists their tags made."""
    sort_names = dict(
        StoryArc.objects.filter(pk__in=list(arc_pks)).values_list("pk", "sort_name")
    )
    if not sort_names:
        return {}
    lists = dict(
        ReadingListSource.objects.filter(
            kind=ReadingListSourceKind.TAGS, ref__in=set(sort_names.values())
        ).values_list("ref", "reading_list_id")
    )
    return {
        arc_pk: lists[sort_name]
        for arc_pk, sort_name in sort_names.items()
        if sort_name in lists
    }


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
            f"{identifier.source_name}:{identifier.id_type}:{identifier.key}"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[missing-attribute]
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
            "collection": "series",
            "pks": pks,
            "page": 1,
        }
        number = obj.issue_number
        ts = self._obj_ts(obj)
        query_params = {
            "ts": ts,
            "topCollection": "publishers",
        }

        return self._publication_belongs_to_link(kwargs, query_params, name, number)

    def _publication_belongs_to_volume(self, obj) -> list:
        volume_name = obj.volume_name
        if volume_name is None:
            return []
        display_name = Volume.to_str(volume_name, obj.volume_number_to) or BLANK_TITLE
        kwargs = {"collection": "volumes", "pks": [obj.volume_id], "page": 1}
        ts = self._obj_ts(obj)
        query_params = {"ts": ts, "topCollection": "publishers"}
        return self._publication_belongs_to_link(
            kwargs, query_params, display_name, volume_name
        )

    def _publication_belongs_to_folder(self, obj) -> list:
        if not self.is_allowed(obj):
            return []
        folder = obj.parent_folder
        # ``parent_folder`` is a nullable forward FK, so it resolves
        # through ``_base_manager`` and no Q or manager can filter it.
        # Guard explicitly, or a visible comic publishes a stamped
        # folder's absolute path plus a dead browse link. The None arm
        # is a live AttributeError today -- ``is_allowed`` is a no-op
        # for a Comic, which is a sibling of Folder rather than a Folder.
        # No staff exemption, matching ``MissingACLFilterMixin``: a
        # stamped folder is hidden from everyone.
        if folder is None or folder.missing_since is not None:
            return []
        name = folder.path
        pks = [folder.pk]
        kwargs = {"collection": "folders", "pks": pks, "page": 1}
        number = None
        ts = self._obj_ts(obj)
        query_params = {"ts": ts, "topCollection": "folders"}

        return self._publication_belongs_to_link(kwargs, query_params, name, number)

    def _publication_belongs_to_reading_lists(self, obj) -> list:
        """
        Link each reading list the comic is in, at its first position.

        Only lists this user may see: another user's personal list is not
        named here, any more than it browses.
        """
        entries = (
            ReadingListEntry.objects.filter(
                GroupACLMixin.reading_list_visibility_filter(
                    self.request.user, "reading_list__"
                ),
                comic_id=obj.pk,
                ignored=False,
            )
            .values_list("reading_list_id", "reading_list__name")
            .annotate(first=Min("position"))
            .order_by("reading_list__sort_name", "reading_list_id")
        )
        ts = self._obj_ts(obj)
        links = []
        for list_pk, list_name, position in entries:
            kwargs = {"collection": "arcs", "pks": [list_pk], "page": 1}
            query_params = {"ts": ts, "topCollection": "arcs"}
            links += self._publication_belongs_to_link(
                kwargs, query_params, list_name or BLANK_TITLE, position + 1
            )
        return links

    def _publication_belongs_to(self, obj) -> dict:
        belongs_to = {}
        if series := self._publication_belongs_to_series(obj):
            belongs_to["series"] = series
        if volume := self._publication_belongs_to_volume(obj):
            belongs_to["volume"] = volume
        if folder := self._publication_belongs_to_folder(obj):
            belongs_to["collection"] = folder
        if reading_lists := self._publication_belongs_to_reading_lists(obj):
            belongs_to["story_arc"] = reading_lists

        return belongs_to

    def _add_tag_link(self, obj: Any, filter_key: str, subfield: str = "") -> None:
        # ``obj`` can be either a real ``NamedModel`` (when called with
        # ``subfield=""``) or a ``SimpleNamespace`` carrying ``pk`` /
        # ``name`` / ``links`` (the partitioned ``_publication_subject``
        # rows). Typing as ``Any`` lets both shapes through; the
        # function only reads ``pk`` / ``name`` and writes ``links``.
        kwargs = {"collection": "series", "pks": (), "page": 1}
        value = getattr(obj, subfield) if subfield else obj
        filters = {filter_key: [value.pk]}
        filters = json.dumps(filters)
        query_params = {
            "topCollection": "series",
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
        rows = list(rows)
        arc_lists = _arc_list_pks(
            row["pk"] for row in rows if row["_kind"] == _STORY_ARC_KIND
        )
        flat_subjs: list[Any] = []
        for row in rows:
            kind = row["_kind"]
            pk = row["pk"]
            if kind == _STORY_ARC_KIND:
                # An arc is a reading list: its link filters by the list.
                pk = arc_lists.get(pk)
            subj = SimpleNamespace(pk=pk, name=row["name"], links=())
            if pk is not None:
                self._add_tag_link(subj, _SUBJECT_FILTER_KEYS[kind])
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
        self._set_layout_and_progression(md, obj.reading_direction)

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
    # The manifest is a Divina webpub manifest, not a feed — serve it under the
    # media type its in-feed ``self`` link advertises (still envelope-free).
    renderer_classes = (OPDS2ManifestRenderer,)

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
    def get_filtered_queryset(self, model, *args, **kwargs):
        """
        Find the manifest's comic by the ACL and its pk alone.

        The saved OPDS browser filters (read state, shelves, search) are
        the last feed's; they say nothing about which book a manifest is
        for, and a book they hide would get a manifest with no reading
        order.
        """
        if model is not Comic:
            return super().get_filtered_queryset(model, *args, **kwargs)
        acl_filter = self.get_acl_filter(Comic, self.request.user)
        return Comic.objects.filter(acl_filter, pk__in=self.kwargs["pks"])

    @override
    def get_object(self) -> MappingProxyType:
        """Get one publication object, or 404 if the user can't see it."""
        book_qs, _, zero_pad = self.get_book_qs()
        # ``_publication_belongs_to_folder`` reads ``obj.parent_folder.path``
        # when folder_view is enabled. Without this join, every manifest
        # hit on a folder-gated install fires one lazy ``Folder.get`` per
        # request (sub-plan 05 #8). Adding the join here keeps the cost
        # scoped to the manifest path — feeds don't need it.
        book_qs = book_qs.select_related("parent_folder")
        obj = book_qs.first()
        if obj is None:
            raise NotFound
        return MappingProxyType(self._publication(obj, zero_pad))
