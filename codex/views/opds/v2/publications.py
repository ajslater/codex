"""Publication Methods for OPDS v2.0 feed."""

from datetime import datetime
from math import floor
from types import MappingProxyType
from urllib.parse import quote_plus

from codex.librarian.covers.create import THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH
from codex.models import Comic
from codex.settings.settings import FALSY
from codex.views.opds.const import AUTHOR_ROLES, MimeType, Rel
from codex.views.opds.util import get_contributors, get_m2m_objects
from codex.views.opds.v2.top_links import HrefData, LinkData, OPDS2TopLinksView

_MD_CONTRIBUTOR_MAP = MappingProxyType(
    {
        "author": AUTHOR_ROLES,
        # "translator": {},
        "editor": {"Editor"},
        "artist": {"CoverArtist"},
        # "illustrator": {},
        "letterer": {"Letterer"},
        "penciller": {"Penciller"},
        "colorist": {"Colorist"},
        "inker": {"Inker"},
    }
)
_CONTRIBUTOR_ROLES = frozenset({x for s in _MD_CONTRIBUTOR_MAP.values() for x in s})


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
        href_data = HrefData(kwargs, query_params, True, "opds:bin:cover")
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
    def _add_contributors(md, pks, key, roles):
        """Add contributors to metadata."""
        if contributors := get_contributors(pks, roles):
            md[key] = contributors

    def _publication_optional_metadata(self, md, obj):
        """Add optional Publication Metadtata."""
        if subtitle := obj.name:
            md["subtitle"] = subtitle
        # if identifier := obj.get("guid")
        #   md["identifier"] = identifier
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
        for key, roles in _MD_CONTRIBUTOR_MAP.items():
            self._add_contributors(md, obj.ids, key, roles)
        if contributors := get_contributors(obj.ids, _CONTRIBUTOR_ROLES, True):
            md["contributor"] = contributors

        if m2m_objs := get_m2m_objects(obj.ids):
            # XXX Subjects can also have links
            # https://readium.org/webpub-manifest/schema/subject-object.schema.json
            subjects = []
            for subjs in m2m_objs.values():
                for subj in subjs:
                    subjects.append(subj.name)
            md["subject"] = subjects

    def _publication_metadata(self, obj, zero_pad):
        title = Comic.get_title(
            obj,
            volume=False,
            name=False,
            zero_pad=zero_pad,
            filename_fallback=self.title_filename_fallback,
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

        # This would be for comic streaming which is not supported by OPDS 2 yet?
        # self_href_data = HrefData(self_kwargs, absolute_query_params=True)
        # self_link_data = LinkData(Rel.SELF, self_href_data, mime_type=MimeType.OPDS_PUB)

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
        links = [
            # Comic streaming link (unsupported)
            # self.link(self_link_data),
            self.link(alt_link_data),
            self.link(acq_link_data),
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
