"""Publication Methods for OPDS v2.0 feed."""

from datetime import datetime
from math import floor
from types import MappingProxyType
from urllib.parse import quote_plus

from codex.librarian.covers.create import THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH
from codex.models import Comic
from codex.settings import FALSY
from codex.views.opds.const import AUTHOR_ROLES, MimeType, Rel
from codex.views.opds.util import get_credits, get_m2m_objects
from codex.views.opds.v2.href import HrefData
from codex.views.opds.v2.links import LinkData
from codex.views.opds.v2.top_links import OPDS2TopLinksView

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
    }
)
_CREDIT_ROLES = frozenset({x for s in _MD_CREDIT_MAP.values() for x in s})


class OPDS2PublicationView(OPDS2TopLinksView):
    """Publication Methods for OPDS 2.0 feed."""

    def _images(self, obj):
        # Images
        kwargs = {"group": obj.group, "pks": obj.ids}
        ts = floor(datetime.timestamp(obj.updated_at))
        query_params = {
            "customCovers": True,
            "dynamicCovers": False,
            "ts": ts,
        }
        href_data = HrefData(
            kwargs, query_params, absolute_query_params=True, url_name="opds:bin:cover"
        )
        link_data = LinkData(
            Rel.THUMBNAIL,
            href_data,
            mime_type=MimeType.WEBP,
            height=THUMBNAIL_HEIGHT,
            width=THUMBNAIL_WIDTH,
        )

        cover_link = self.link(link_data)

        link_data.rel = Rel.IMAGE

        image_link = self.link(link_data)

        return [
            cover_link,
            image_link,
        ]

    @staticmethod
    def _add_credits(md, pks, key, roles):
        """Add credits to metadata."""
        if credit_objs := get_credits(pks, roles, exclude=False):
            md[key] = credit_objs

    def _publication_optional_metadata(self, md, obj):
        """Add optional Publication Metadtata."""
        if subtitle := obj.name:
            md["subtitle"] = subtitle
        if desc := obj.summary:
            md["description"] = desc
        if lang := obj.language:
            md["language"] = str(lang)
        if publisher := obj.publisher_name:
            md["publisher"] = publisher
        if imprint := obj.imprint_name:
            md["imprint"] = imprint
        if nop := obj.page_count:
            md["number_of_pages"] = nop

    def _publication_extended_metadata(self, md, obj):
        """Publication m2m metadata only on the metadata alternate link."""
        for key, roles in _MD_CREDIT_MAP.items():
            self._add_credits(md, obj.ids, key, roles)
        if credit_objs := get_credits(obj.ids, _CREDIT_ROLES, exclude=True):
            md["credit"] = credit_objs

        if m2m_objs := get_m2m_objects(obj.ids):
            # Subjects can also have links
            # https://readium.org/webpub-manifest/schema/subject-object.schema.json
            md["subject"] = [subj.name for subjs in m2m_objs.values() for subj in subjs]

    def _publication_metadata(self, obj, zero_pad):
        title = Comic.get_title(
            obj,
            volume=False,
            name=False,
            filename_fallback=self.title_filename_fallback,
            zero_pad=zero_pad,
        )
        md = {
            "type": MimeType.BOOK,
            "modified": obj.updated_at,
            "published": obj.date,
            "title": title,
        }
        self._publication_optional_metadata(md, obj)
        if self.request.GET.get("opdsMetadata", "").lower() not in FALSY:
            self._publication_extended_metadata(md, obj)
        return md

    def _publication(self, obj, zero_pad):
        pub = {}
        pub["metadata"] = self._publication_metadata(obj, zero_pad)

        fn = quote_plus(obj.get_filename())

        download_mime_type = MimeType.FILE_TYPE_MAP.get(obj.file_type, MimeType.OCTET)
        self_kwargs = {"pk": obj.pk, "page": 1}

        alt_kwargs = self_kwargs
        alt_href_data = HrefData(
            alt_kwargs,
            {"opdsMetadata": 1},
            absolute_query_params=True,
            url_name="opds:v2:acq",
        )
        alt_link_data = LinkData(
            Rel.ALTERNATE, alt_href_data, mime_type=MimeType.OPDS_PUB
        )

        acq_kwargs = {"pk": obj.pk, "filename": fn}
        acq_href_data = HrefData(
            acq_kwargs,
            url_name="opds:bin:download",
            absolute_query_params=True,
        )

        acq_link_data = LinkData(
            Rel.ACQUISITION,
            acq_href_data,
            mime_type=download_mime_type,
        )
        prog_kwargs = {"group": "c", "pk": obj.pk}
        prog_href_data = HrefData(prog_kwargs, url_name="opds:v2:position")

        auth_href_data = HrefData({}, url_name="opds:authentication:v1")
        auth_link_data = LinkData(
            Rel.AUTHENTICATION,
            auth_href_data,
            mime_type=MimeType.AUTHENTICATION,
        )
        auth_link = self.link(auth_link_data)

        prog_link_data = LinkData(
            Rel.PROGRESSION,
            prog_href_data,
            mime_type=MimeType.PROGRESSION,
            authenticate=auth_link,
        )
        links = [
            self.link(alt_link_data),
            self.link(acq_link_data),
            self.link(prog_link_data),
        ]
        pub["links"] = links

        images = self._images(obj)
        pub["images"] = images

        return pub

    def get_publications(self, book_qs, zero_pad, title):
        """Get publications section."""
        groups = []
        publications = []
        self.title_filename_fallback = bool(self.admin_flags.get("folder_view"))
        for obj in book_qs:
            pub = self._publication(obj, zero_pad)
            publications.append(pub)

        if publications:
            pub_group = {
                "metadata": {
                    "title": title,
                    "subtitle": "Books",
                },
                "links": [self.link_self()],
                "publications": publications,
            }
            groups.append(pub_group)
        return groups
