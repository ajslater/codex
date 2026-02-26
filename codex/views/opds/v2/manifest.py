"""Publication Methods for OPDS v2.0 feed."""

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from math import floor
from types import MappingProxyType

from django.db.models import F, QuerySet
from typing_extensions import override

from codex.models.base import BaseModel, NamedModel
from codex.models.identifier import Identifier
from codex.models.named import Credit, StoryArcNumber
from codex.serializers.opds.v2.publication import (
    OPDS2PublicationDivinaManifestSerializer,
)
from codex.views.auth import GroupACLMixin
from codex.views.opds.const import AUTHOR_ROLES, BLANK_TITLE, MimeType, Rel
from codex.views.opds.metadata import get_credits, get_m2m_objects
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
        query_params = {
            "ts": ts,
            "topGroup": "p",
        }

        return self._publication_belongs_to_link(kwargs, query_params, name, number)

    def _publication_belongs_to_folder(self, obj) -> list:
        if not self.is_allowed(obj):
            return []
        folder = obj.parent_folder
        name = folder.path
        pks = [folder.pk]
        kwargs = {"group": "f", "pks": pks, "page": 1}
        number = None
        ts = floor(datetime.timestamp(obj.updated_at))
        query_params = {"ts": ts, "topGroup": "f"}

        return self._publication_belongs_to_link(kwargs, query_params, name, number)

    def _publication_belongs_to_story_arcs(self, obj) -> list:
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
            name = story_arc.name or BLANK_TITLE
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

    def _publication_belongs_to(self, obj) -> dict:
        belongs_to = {}
        if series := self._publication_belongs_to_series(obj):
            belongs_to["series"] = series
        if folder := self._publication_belongs_to_folder(obj):
            belongs_to["collection"] = folder
        if story_arcs := self._publication_belongs_to_story_arcs(obj):
            belongs_to["storyArc"] = story_arcs

        return belongs_to

    def _add_tag_link(self, obj: BaseModel, filter_key: str, subfield: str = ""):
        kwargs = {"group": "s", "pks": (), "page": 1}
        value: NamedModel = getattr(obj, subfield) if subfield else obj  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
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
        obj.links = (link,)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]

    def _publication_subject(self, obj) -> tuple[NamedModel, ...]:
        m2m_objs = get_m2m_objects(obj.ids)
        flat_subjs = []
        for key, subjs in m2m_objs.items():
            filter_key = key + "s"
            for subj in subjs:
                self._add_tag_link(subj, filter_key)
                flat_subjs.append(subj)
        return tuple(flat_subjs)

    def _add_credits(self, pks, roles) -> QuerySet[Credit] | None:
        """Add credits to metadata."""
        if credit_objs := get_credits(pks, roles, exclude=False):
            for credit_obj in credit_objs:
                self._add_tag_link(credit_obj, "credits", "person")
            return credit_objs
        return None

    def _publication_credits(self, obj) -> Mapping[str, tuple[Credit, ...]]:
        credit_md = {}
        for key, roles in _MD_CREDIT_MAP.items():
            if credit_objs := self._add_credits(obj.ids, roles):
                credit_md[key] = credit_objs
        return credit_md

    @override
    def _publication_metadata(self, obj, zero_pad) -> dict:
        md = super()._publication_metadata(obj, zero_pad)
        if desc := obj.summary:
            md["description"] = desc
        if lang := obj.language:
            md["language"] = lang.name
        if publisher := obj.publisher_name:
            md["publisher"] = publisher
        if imprint := obj.imprint_name:
            md["imprint"] = imprint
        if layout := obj.reading_direction:
            md["layout"] = layout if layout != "ttb" else "scrolled"
        if identifier := self._publication_identifier(obj):
            md["identifier"] = identifier
        if belongs_to := self._publication_belongs_to(obj):
            md["belongs_to"] = belongs_to
        if subject := self._publication_subject(obj):
            md["subject"] = subject
        if credit_md := self._publication_credits(obj):
            md.update(credit_md)
        return md


class OPDS2ManifestView(OPDS2ManifestMetadataView):
    """Single publication manifest view."""

    serializer_class = OPDS2PublicationDivinaManifestSerializer

    def _publication_reading_order(self, obj) -> list:
        """
        Reader manifest for OPDS 2.0.

        This part of the spec is redundant, but required.
        """
        reading_order = []
        if not obj:
            return reading_order
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
                # type is required, but not calculated for efficiency.
                "type": MimeType.JPEG,
                # height and width not pre-calculated and fortunately not required by Stump
            }
            reading_order.append(page)
        return reading_order

    def _cover(self, obj) -> list:
        images = []
        if not obj:
            return images
        ts = floor(datetime.timestamp(obj.updated_at))
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
        obj = book_qs.first()
        return MappingProxyType(self._publication(obj, zero_pad))
