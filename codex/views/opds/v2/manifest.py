"""Publication Methods for OPDS v2.0 feed."""

from datetime import datetime
from math import floor
from types import MappingProxyType

from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.serializers.opds.v2.publication import (
    OPDS2PublicationDivinaManifestSerializer,
)
from codex.views.opds.const import MimeType, Rel
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

    def _publication_belongs_to(self, obj):
        name = obj.series_name if obj.series.name else self.EMPTY_TITLE
        pks = [obj.series.pk]
        number = obj.issue_number
        kwargs = {"group": "s", "pks": pks, "page": 1}
        ts = floor(datetime.timestamp(obj.updated_at))
        query_params = {"ts": ts}
        href_data = HrefData(
            kwargs,
            query_params,
            url_name="opds:v2:feed",
        )
        link_data = LinkData(Rel.SUB, href_data, mime_type=MimeType.OPDS_JSON)
        link = self.link(link_data)
        return {"series": [{"name": name, "position": number, "links": [link]}]}

    @override
    def _publication(self, obj, zero_pad):
        pub = super()._publication(obj, zero_pad)
        pub["metadata"]["conformsTo"] = (
            "https://readium.org/webpub-manifest/profiles/divina"
        )
        if belongs_to := self._publication_belongs_to(obj):
            pub["metadata"]["belongs_to"] = belongs_to
        pub["resources"] = self._cover(obj)
        pub["reading_order"] = self._publication_reading_order(obj)
        return pub

    @override
    def get_object(self):
        """Get one publication object."""
        book_qs, _, zero_pad = self.get_book_qs()
        obj = book_qs.first()
        return MappingProxyType(self._publication(obj, zero_pad))
