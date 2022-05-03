"""Mimic comicbox.ComicArchive functions for PDFs."""
from io import BytesIO
from logging import CRITICAL
from pathlib import Path
from typing import Optional, Union

from comicbox.metadata.filename import FilenameMetadata
from filetype import guess
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError
from pdfrw import PdfReader, PdfWriter
from pdfrw.errors import log as pdfrw_log

from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class PDF:
    """PDF class."""

    COVER_PAGE_INDEX = 1
    MIME_TYPE = "application/pdf"

    @classmethod
    def is_pdf(cls, path):
        """Is the path a pdf."""
        kind = guess(path)
        return kind and kind.mime == cls.MIME_TYPE

    def __init__(self, path: Union[Path, str], **_kwargs):
        """Initialize."""
        self._path: Path = Path(path)
        self._reader: Optional[PdfReader] = None
        self._metadata: dict = {}

    def __enter__(self):
        """Context enter."""
        return self

    def __exit__(self, *_args):
        """Context exit."""
        self.close()

    def _get_reader(self) -> PdfReader:
        """Lazily get the pdfrw reader."""
        if not self._reader:
            # Turn off error logging for pdfrw
            loglevel = pdfrw_log.getEffectiveLevel()
            pdfrw_log.setLevel(CRITICAL)
            self._reader = PdfReader(self._path)
            pdfrw_log.setLevel(loglevel)
        return self._reader

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
                root = self._get_reader().Root
                self._metadata["page_count"] = root.Pages.Count  # type: ignore
            except Exception as exc:
                LOG.warning(f"Error reading number of pages for {self._path}: {exc}")
                self._metadata["page_count"] = 100

        return self._metadata

    def get_page_by_index(self, index) -> bytes:
        """Get the page bytestream by index."""
        page = self._get_reader().getPage(index)
        writer = PdfWriter()
        writer.addpage(page)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def get_cover_image(self) -> bytes:
        """Get the first page as a image data."""
        image_data = b""
        try:
            images = convert_from_path(
                self._path,
                first_page=self.COVER_PAGE_INDEX,
                last_page=self.COVER_PAGE_INDEX,
                thread_count=4,
                fmt="tiff",  # tiff is fastest.
                use_pdftocairo=True,
            )
            # pdf2image returns PIL Images :/
            with BytesIO() as buf:
                if images:
                    image = images[0]
                    image.save(buf, image.format)
                    for image in images:
                        image.close()
                image_data = buf.getvalue()
        except PDFInfoNotInstalledError as exc:
            raise FileNotFoundError(str(exc)) from exc

        return image_data

    def close(self):
        """Get rid of the reader."""
        self._reader = None
