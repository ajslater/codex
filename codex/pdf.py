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
from PIL.Image import Image as ImageType

from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class PDF:
    """PDF class."""

    COVER_PAGE_INDEX = 1
    MIME_TYPE = "application/pdf"

    def __init__(self, path: Union[Path, str]):
        """Initialize."""
        self._path: Path = Path(path)
        self._reader: Optional[PdfReader] = None
        self._metadata: dict = {}

    def is_pdf(self):
        """Is the path a pdf."""
        kind = guess(self._path)
        return kind and kind.mime == self.MIME_TYPE

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

    def get_cover_image_as_pil(self) -> ImageType:
        """Get the first page as a image data."""
        try:
            images = convert_from_path(
                self._path,
                first_page=self.COVER_PAGE_INDEX,
                last_page=self.COVER_PAGE_INDEX,
                thread_count=4,
                fmt="tiff",  # tiff fastest, maybe lossless.
                use_pdftocairo=True,
            )

            return images[0]
        except PDFInfoNotInstalledError as exc:
            raise FileNotFoundError(str(exc)) from exc

    def close(self):
        """Get rid of the reader."""
        self._reader = None
