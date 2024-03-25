"""Publication Methods for OPDS v2.0 feed."""

from types import MappingProxyType
from urllib.parse import quote_plus

from django.contrib.staticfiles.storage import staticfiles_storage

from codex.librarian.covers.create import CoverCreateMixin
from codex.models import Comic
from codex.views.opds.const import AUTHOR_ROLES, MimeType, Rel
from codex.views.opds.util import get_contributors, get_m2m_objects
from codex.views.opds.v2.links import HrefData, LinkData, LinksMixin


class PublicationMixin(LinksMixin):
    """Publication Methods for OPDS 2.0 feed."""

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
    is_opds_metadata = False

    def _get_big_image_link(self, obj, cover_pk):
        if cover_pk:
            mime_type = MimeType.JPEG
            url_name = "opds:bin:page"
            href = None
            min_page = 0
            max_page = obj.max_page or 1
        else:
            mime_type = MimeType.WEBP
            href = staticfiles_storage.url("img/missing_cover.webp")
            url_name = None
            min_page = None
            max_page = None

        kwargs = {"pk": obj.pk, "page": 0}
        href_data = HrefData(
            kwargs,
            absolute_query_params=True,
            url_name=url_name,
            min_page=min_page,
            max_page=max_page,
        )
        link_data = LinkData(Rel.IMAGE, href_data, href=href, mime_type=mime_type)
        return self.link(link_data)

    def _images(self, obj):
        # Images
        cover_pk = obj.cover_pk

        kwargs = {"pk": cover_pk}
        href_data = HrefData(
            kwargs, url_name="opds:bin:cover", absolute_query_params=True
        )
        link_data = LinkData(
            Rel.THUMBNAIL,
            href_data,
            mime_type=MimeType.WEBP,
            height=CoverCreateMixin.THUMBNAIL_HEIGHT,
            width=CoverCreateMixin.THUMBNAIL_WIDTH,
        )

        cover_link = self.link(link_data)

        image_link = self._get_big_image_link(obj, cover_pk)

        return [
            cover_link,
            image_link,
        ]

    @staticmethod
    def _add_contributors(md, pk, key, roles):
        """Add contributors to metadata."""
        if contributors := get_contributors(pk, roles):
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
        for key, roles in self._MD_CONTRIBUTOR_MAP.items():
            self._add_contributors(md, obj.pk, key, roles)
        if contributors := get_contributors(obj.pk, self._CONTRIBUTOR_ROLES, True):
            md["contributor"] = contributors

        if m2m_objs := get_m2m_objects(obj.pk):
            # XXX Subjects can also have links
            # https://readium.org/webpub-manifest/schema/subject-object.schema.json
            subjects = []
            for subjs in m2m_objs.values():
                for subj in subjs:
                    subjects.append(subj.name)
            md["subject"] = subjects

    def _publication_metadata(self, obj, issue_number_max):
        title = Comic.get_title(
            obj, volume=False, name=False, issue_number_max=issue_number_max
        )
        md = {
            "type": MimeType.BOOK,
            "modified": obj.updated_at,
            "published": obj.date,
            "title": title,
        }
        self._publication_optional_metadata(md, obj)
        if self.is_opds_metadata:
            self._publication_extended_metadata(md, obj)
        return md

    def _publication(self, obj, issue_number_max):
        pub = {}
        pub["metadata"] = self._publication_metadata(obj, issue_number_max)

        fn = Comic.get_filename(obj)
        fn = quote_plus(fn)

        download_mime_type = MimeType.FILE_TYPE_MAP.get(obj.file_type, MimeType.OCTET)
        self_kwargs = {"group": "c", "pk": obj.pk, "page": 1}
        self_href_data = HrefData(self_kwargs, absolute_query_params=True)
        self_link_data = LinkData(Rel.SELF, self_href_data, mime_type=MimeType.OPDS_PUB)

        alt_kwargs = self_kwargs
        alt_href_data = HrefData(
            alt_kwargs, {"opdsMetadata": 1}, absolute_query_params=True
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
            self.link(self_link_data),
            self.link(alt_link_data),
            self.link(acq_link_data),
        ]
        pub["links"] = links

        images = self._images(obj)
        pub["images"] = images

        return pub

    def get_publications(self, book_qs, issue_number_max, title):
        """Get publications section."""
        groups = []
        publications = []
        for obj in book_qs:
            pub = self._publication(obj, issue_number_max)
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
