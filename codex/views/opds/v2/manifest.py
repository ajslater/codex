"""Publication Methods for OPDS v2.0 feed."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from math import floor
from types import MappingProxyType

from django.db.models import F
from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.models.identifier import Identifier
from codex.models.named import StoryArcNumber
from codex.serializers.opds.v2.publication import (
    OPDS2PublicationDivinaManifestSerializer,
)
from codex.views.auth import GroupACLMixin
from codex.views.opds.const import BLANK_TITLE, MimeType, Rel
from codex.views.opds.v2.feed.links import LinkData
from codex.views.opds.v2.feed.publications import OPDS2PublicationBaseView
from codex.views.opds.v2.href import HrefData


class OPDS2ManifestView(OPDS2PublicationBaseView):
    """Single publication manifest view."""

    TARGET: str = "opds2"
    throttle_scope = "opds"
    serializer_class: type[BaseSerializer] | None = (
        OPDS2PublicationDivinaManifestSerializer
    )

    def _publication_identifier(self, obj):
        rel = GroupACLMixin.get_rel_prefix(Identifier)
        comic_filter = {rel + "in": [obj.pk]}
        identifiers = (
            Identifier.objects.filter(**comic_filter)
            .annotate(source_name=F("source__name"))
            .only("id_type", "key")
            .order_by("source_name", "key")
        )
        urns = []
        for identifier in identifiers:
            urn = f"{identifier.source_name}:{identifier.id_type}:{identifier.key}"  # pyright: ignore[reportAttributeAccessIssue]
            urns.append(urn)
        return ",".join(urns)

    def _publication_belongs_to_link(
        self,
        kwargs: Mapping[str, str | int | Sequence[int]],
        query_params: Mapping[str, str | int | Mapping],
        name: str,
        number: int | None,
    ):
        href_data = HrefData(
            kwargs,
            query_params,
            url_name="opds:v2:feed",
        )
        link_data = LinkData(Rel.SUB, href_data, mime_type=MimeType.OPDS_JSON)
        link = self.link(link_data)
        belongs_to: dict[str, str | list | int] = {"name": name, "links": [link]}
        if number:
            belongs_to["number"] = number
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
        ts = floor(datetime.timestamp(obj.updated_at))
        query_params = {"ts": ts, "topGroup": "p"}

        return self._publication_belongs_to_link(kwargs, query_params, name, number)

    def _publication_belongs_to_folder(self, obj):
        if not self.is_allowed(obj):
            return []
        name = obj.path
        pks = [obj.parent_folder.pk]
        kwargs = {"group": "f", "pks": pks, "page": 1}
        number = None
        ts = floor(datetime.timestamp(obj.updated_at))
        query_params = {"ts": ts, "topGroup": "f"}

        return self._publication_belongs_to_link(kwargs, query_params, name, number)

    def _publication_belongs_to_story_arcs(self, obj):
        story_arcs = []
        rel = GroupACLMixin.get_rel_prefix(StoryArcNumber)
        comic_filter = {rel + "in": [obj.pk]}
        story_arc_numbers = (
            StoryArcNumber.objects.filter(**comic_filter)
            .only("story_arc", "number")
            .order_by("story_arc__name")
        )
        for story_arc_number in story_arc_numbers:
            story_arc = story_arc_number.story_arc
            name = story_arc.name if story_arc.name else BLANK_TITLE
            pks = [story_arc.pk]
            number = story_arc_number.number
            kwargs = {"group": "a", "pks": pks, "page": 1}
            ts = floor(datetime.timestamp(obj.updated_at))
            query_params = {"ts": ts, "topGroup": "a"}

            story_arc = self._publication_belongs_to_link(
                kwargs, query_params, name, number
            )
            story_arcs += story_arc
        return story_arcs

    def _publication_belongs_to(self, obj):
        belongs_to = {}
        if series := self._publication_belongs_to_series(obj):
            belongs_to["series"] = series
        if folder := self._publication_belongs_to_folder(obj):
            belongs_to["collection"] = folder
        if story_arcs := self._publication_belongs_to_story_arcs(obj):
            belongs_to["storyArc"] = story_arcs

        return belongs_to

    def _publication_reading_order(self, obj):
        """
        Reader manifest for OPDS 2.0.

        This part of the spec is redundant, but required.
        """
        reading_order = []
        ts = floor(datetime.timestamp(obj.updated_at))
        query_params = {"ts": ts}
        for page_num in range(obj.page_count):
            kwargs = {"pk": obj.pk, "page": page_num}
            href_data = HrefData(
                kwargs,
                query_params,
                url_name="opds:bin:page",
                min_page=0,
                max_page=obj.page_count,
            )
            href = self.href(href_data)
            page = {
                "href": href,
                "type": MimeType.JPEG,  # required, but not actually calculated
                # height and width not pre-calculated and fortunately not required by Stump
            }
            reading_order.append(page)
        return reading_order

    @override
    def _publication_extended_metadata(self, md, obj):
        super()._publication_extended_metadata(md, obj)
        if identifier := self._publication_identifier(obj):
            md["identifier"] = identifier
        if belongs_to := self._publication_belongs_to(obj):
            md["belongs_to"] = belongs_to

    @override
    def _publication_metadata(self, obj, zero_pad):
        md = super()._publication_metadata(obj, zero_pad)
        md["conformsTo"] = "https://readium.org/webpub-manifest/profiles/divina"
        return md

    @override
    def _publication(self, obj, zero_pad):
        pub = super()._publication(obj, zero_pad)
        pub["resources"] = self._cover(obj)
        pub["reading_order"] = self._publication_reading_order(obj)
        return pub

    @override
    def get_object(self):
        """Get one publication object."""
        book_qs, _, zero_pad = self.get_book_qs()
        obj = book_qs.first()
        return MappingProxyType(self._publication(obj, zero_pad))
