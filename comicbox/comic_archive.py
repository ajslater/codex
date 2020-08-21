"""
Comic archive.

Reads and writes metadata via the included metadata package.
Reads data using libarchive via archi.
"""

import zipfile

from pathlib import Path

import rarfile

from .metadata import comicapi
from .metadata.comet import CoMet
from .metadata.comic_base import IMAGE_EXT_RE
from .metadata.comic_base import ComicBaseMetadata
from .metadata.comic_xml import ComicXml
from .metadata.comicbookinfo import ComicBookInfo
from .metadata.comicinfoxml import ComicInfoXml
from .metadata.filename import FilenameMetadata


RECOMPRESS_SUFFIX = ".comicbox_tmp_zip"
CBZ_SUFFIX = ".cbz"


class Settings:
    """Settings to control default behavior. Overridden by cli namespace."""

    comicrack = True
    comiclover = True
    comet = True
    filename = True
    raw = False


class ComicArchive(object):
    """
    Represent a comic archive.

    Contains the compressed archive file and its parsed metadata
    """

    PARSER_CLASSES = (ComicInfoXml, ComicBookInfo, CoMet)
    FILENAMES = set((CoMet.FILENAME, ComicInfoXml.FILENAME))

    def __init__(self, path, metadata=None, settings=None):
        """Initialize the archive with a path to the archive."""
        if settings is None:
            settings = Settings()
        self.settings = settings
        self.set_path(path)
        self.metadata = ComicBaseMetadata(metadata=metadata)
        self.raw = {}
        if metadata is None:
            self._parse_metadata()
        self.metadata.compute_page_metadata(self.namelist())

    def set_path(self, path):
        """Set the path and determine the archive type."""
        self._path = Path(path)
        if zipfile.is_zipfile(self._path):
            self.archive_cls = zipfile.ZipFile
        elif rarfile.is_rarfile(self._path):
            self.archive_cls = rarfile.RarFile
        else:
            raise ValueError(f"Unsupported archive type: {self._path}")

    def _get_archive(self, mode="r"):
        return self.archive_cls(self._path, mode=mode)

    def get_path(self):
        """Get the path for the archive."""
        return self._path

    def namelist(self):
        """Get the archive file namelist."""
        with self._get_archive() as archive:
            return sorted(archive.namelist())

    def _parse_metadata_entries(self):
        """Get the filenames and file based metadata."""
        cix_md = {}
        comet_md = {}
        with self._get_archive() as archive:
            for fn in sorted(archive.namelist()):
                basename = Path(fn).name.lower()
                xml_parser_cls = None
                if (
                    basename == ComicInfoXml.FILENAME.lower()
                    and self.settings.comicrack
                ):
                    md = cix_md
                    xml_parser_cls = ComicInfoXml
                    title = "ComicRack"
                elif basename == CoMet.FILENAME.lower() and self.settings.comet:
                    md = comet_md
                    xml_parser_cls = CoMet
                    title = "CoMet"
                if not xml_parser_cls:
                    continue
                with archive.open(fn) as md_file:
                    data = md_file.read()
                    if self.settings.raw:
                        self.raw[title] = data
                    parser = xml_parser_cls(string=data)
                    md.update(parser.metadata)
        return cix_md, comet_md

    def get_archive_comment(self):
        """Get the comment field from an archive."""
        with self._get_archive() as archive:
            comment = archive.comment
            if isinstance(archive, zipfile.ZipFile):
                comment = comment.decode()
        return comment

    def _parse_metadata_comments(self):
        if not self.settings.comiclover:
            return {}
        comment = self.get_archive_comment()
        parser = ComicBookInfo(string=comment)
        cbi_md = parser.metadata
        if self.settings.raw:
            self.raw["ComicLover"] = comment
        return cbi_md

    def _parse_metadata_filename(self):
        if not self.settings.filename:
            return {}
        parser = FilenameMetadata(path=self._path)
        if self.settings.raw:
            self.raw["Filename"] = self._path.name
        return parser.metadata

    def _parse_metadata(self):
        cix_md, comet_md = self._parse_metadata_entries()
        cbi_md = self._parse_metadata_comments()
        filename_md = self._parse_metadata_filename()

        # order of the md list is very important, lowest to highest
        # precedence.
        md_list = (filename_md, comet_md, cbi_md, cix_md)
        self.metadata.synthesize_metadata(md_list)

    def get_num_pages(self):
        """Retun the number of pages."""
        return self.metadata.get_num_pages()

    def get_pages(self, page_from):
        """Get all pages starting with page number."""
        # TODO turn into generator
        pagenames = self.metadata.get_pagenames_from(page_from)
        pages = []
        with self._get_archive() as archive:
            for pagename in pagenames:
                with archive.open(pagename) as page:
                    pages += [page.read()]
        return pages

    def get_page_by_filename(self, filename):
        """Return data for a single page by filename."""
        with self._get_archive() as archive:
            with archive.open(filename) as page:
                return page.read()

    def get_page_by_index(self, index):
        """Get the page data by index."""
        filename = self.metadata.get_pagename(index)
        return self.get_page_by_filename(filename)

    def extract_pages(self, page_from, root_path="."):
        """Extract pages from archive and write to a path."""
        filenames = self.metadata.get_pagenames_from(page_from)
        with self._get_archive() as archive:
            for fn in filenames:
                with archive.open(fn) as page:
                    fn = root_path / fn
                    with open(fn, "wb") as page_file:
                        page_file.write(page.read())

    def extract_cover_as(self, path):
        """Extract the cover image to a destination file."""
        cover_fn = self.metadata.get_cover_page_filename()
        with self._get_archive() as archive:
            with archive.open(cover_fn) as page:
                with open(path, "wb") as cover_file:
                    cover_file.write(page.read())

    def get_cover_image(self):
        """Return cover image data."""
        cover_fn = self.metadata.get_cover_page_filename()
        with self._get_archive() as archive:
            data = archive.read(cover_fn)
        return data

    def get_metadata(self):
        """Return the metadata from the archive."""
        return self.metadata.metadata

    def recompress(self, filename=None, data=None, delete=False, delete_rar=False):
        """Recompress the archive optionally replacing a file."""
        new_path = self._path.with_suffix(CBZ_SUFFIX)
        if new_path.is_file() and new_path != self._path:
            raise ValueError(f"{new_path} already exists.")

        tmp_path = self._path.with_suffix(RECOMPRESS_SUFFIX)
        with self._get_archive() as archive:
            if delete:
                comment = b""
            else:
                comment = archive.comment
            if isinstance(comment, str):
                comment = comment.encode()
            with zipfile.ZipFile(
                tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as zf:
                skipnames = set(filename)
                if delete:
                    skipnames.add(self.FILENAMES)
                for info in sorted(archive.infolist(), key=lambda i: i.filename):
                    if info.filename.lower() in skipnames:
                        continue
                    if IMAGE_EXT_RE.search(info.filename) is None:
                        compress = zipfile.ZIP_DEFLATED
                    else:
                        # images usualy end up slightly larger with
                        # zip compression
                        compress = zipfile.ZIP_STORED
                    zf.writestr(
                        info,
                        archive.read(info),
                        compress_type=compress,
                        compresslevel=9,
                    )
                if filename:
                    zf.writestr(filename, data)
                zf.comment = comment

        old_path = self._path
        tmp_path.replace(new_path)
        self._path = new_path
        if delete_rar:
            print(f"converted to: {new_path}")

        if delete_rar and new_path.is_file():
            old_path.unlink()
            print(f"removed: {old_path}")

    def delete_tags(self):
        """Recompress, without any tag formats."""
        self.recompress(delete=True)

    def write_metadata(self, md_class, recompute_page_sizes=True):
        """Write metadata using the supplied parser class."""
        parser = md_class(metadata=self.get_metadata())
        if recompute_page_sizes and isinstance(parser, ComicInfoXml):
            self.compute_pages_tags()
        if isinstance(parser, (ComicXml, CoMet)):
            self.recompress(parser.FILENAME, parser.to_string())
        elif isinstance(parser, ComicBookInfo):
            with self._get_archive("a") as archive:
                comment = parser.to_string().encode()
                archive.comment = comment
        else:
            raise ValueError(f"Unsupported metadata writer {md_class}")

    def to_comicapi(self):
        """Export to comicapi style metadata."""
        return comicapi.export(self.get_metadata())

    def import_file(self, filename):
        """Try to import metada from a file and then write it into the comic."""
        from xml.etree.ElementTree import ParseError

        from simplejson.errors import JSONDecodeError

        path = Path(filename)
        success_class = None
        for cls in self.PARSER_CLASSES:
            try:
                md = cls(path=path)
                success_class = cls
                break
            except (ParseError, JSONDecodeError):
                pass
        if success_class:
            self.metadata.metadata = md.metadata
            self.write_metadata(success_class)

    def export_files(self):
        """Export metadata to all supported file formats."""
        for cls in self.PARSER_CLASSES:
            md = cls(self.get_metadata())
            fn = self.settings.root_path / cls.FILENAME
            md.to_file(fn)

    def compute_pages_tags(self):
        """Recompute the tag image sizes for ComicRack."""
        with self._get_archive() as archive:
            infolist = archive.infolist()
        parser = ComicInfoXml(metadata=self.get_metadata())
        parser.compute_pages_tags(infolist)
        self.metadata.metadata["pages"] = parser.metadata.get("pages")

    def compute_page_count(self):
        """Compute the page count from images in the archive."""
        self.metadata.compute_page_count()

    def rename_file(self):
        """Rename the archive."""
        car = FilenameMetadata(self.metadata)
        self._path = car.to_file(self._path)

    def print_raw(self):
        """Print raw metadtata."""
        for key, val in self.raw.items():
            print("-" * 10, key, "-" * 10)
            if isinstance(val, bytes):
                val = val.decode()
            print(val)
