"""Mimic comicbox.ComicArchive functions for PDFs."""
from io import BytesIO
from pathlib import Path
from typing import Union

import fitz
from comicbox.metadata.filename import FilenameMetadata
from filetype import guess

from codex.logger.logging import get_logger

LOG = get_logger(__name__)


class PDF:
    """PDF class."""

    COVER_PAGE_INDEX = 1
    _SUFFIX = ".pdf"
    _FILE_TYPE = "PDF"
    MIME_TYPE = "application/pdf"
    _METADATA_KEY_MAP = {
        "tags": "keywords",
        "name": "title",
        "": "subject",
    }

    @classmethod
    def is_pdf(cls, path):
        """Is the path a pdf."""
        if Path(path).suffix.lower() == cls._SUFFIX:
            return True
        kind = guess(path)
        return kind and kind.mime == cls.MIME_TYPE

    def __init__(self, path: Union[Path, str], **_kwargs):
        """Initialize."""
        self._path: Path = Path(path)
        self._doc = None
        self._metadata: dict = {}

    def __enter__(self):
        """Context enter."""
        return self

    def __exit__(self, *_args):
        """Context exit."""
        self.close()

    def _get_doc(self):
        if not self._doc:
            self._doc = fitz.Document(self._path)
        return self._doc

    def _set_metadata_key(self, comicbox_key, pdf_key):
        metadata = self._get_doc().metadata
        if not metadata:
            return
        value = metadata.get(pdf_key)
        if value:
            if comicbox_key == "writer":
                if "creators" not in self._metadata:
                    self._metadata["creators"] = []
                creator = {
                    "role": comicbox_key,
                    "person": value,
                }
                self._metadata["creators"].append(creator)
            else:
                self._metadata[comicbox_key] = value

    def get_file_type(self):
        """Return the file type like comicbox."""
        return self._FILE_TYPE

    def get_metadata(self) -> dict:
        """Get metadata from pdf."""
        if not self._metadata:
            try:
                self._metadata = FilenameMetadata(
                    path=self._path, string=self._path.name
                ).metadata
            except Exception as exc:
                LOG.warning(f"Error reading filename metadata for {self._path}: {exc}")
            try:
                doc = self._get_doc()
                self._metadata["page_count"] = doc.page_count
                for comicbox_key, pdf_key in self._METADATA_KEY_MAP.items():
                    self._set_metadata_key(comicbox_key, pdf_key)
            except Exception as exc:
                LOG.warning(f"Error reading metadata for {self._path}: {exc}")
                self._metadata["page_count"] = 100

        return self._metadata

    def get_page_by_index(self, index) -> bytes:
        """Get the page bytestream by index."""
        doc = self._get_doc()
        doc.select((index,))
        buffer = BytesIO()
        doc.save(buffer)
        self._doc = None
        return buffer.getvalue()

    def get_cover_image(self) -> bytes:
        """Get the first page as a image data."""
        # image_data = b""
        doc = self._get_doc()
        page = doc.load_page(0)
        pix = page.get_pixmap()
        return pix.tobytes(output="ppm")

    def close(self):
        """Get rid of the reader."""
        self._reader = None
