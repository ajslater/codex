"""Mimic comicbox.ComicArchive functions for PDFs."""
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

from comicbox.metadata.filename import FilenameMetadata
from pdf2image import convert_from_path
from pdfrw import PdfReader, PdfWriter

from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class PDF:
    """PDF class."""

    COVER_PAGE_INDEX = 1

    def __init__(self, path: Union[Path, str]):
        """Initialize."""
        self._path: Path = Path(path)
        self._reader: Optional[PdfReader] = None
        self._metadata: dict = {}
        self._cover_image_data: Optional[bytes] = None

    def _get_reader(self) -> PdfReader:
        """Lazily get the pdfrw reader."""
        if not self._reader:
            self._reader = PdfReader(self._path)
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
        if not self._cover_image_data:
            pil_images = convert_from_path(
                self._path,
                first_page=self.COVER_PAGE_INDEX,
                last_page=self.COVER_PAGE_INDEX,
                thread_count=4,
                fmt="jpeg",  # TODO experiment with types
                use_pdftocairo=True,
            )
            image = pil_images[0]
            print(f"{type(image)}")
            buffer = BytesIO()
            image.save(buffer, "JPEG")
            self._cover_image_data = buffer.getvalue()
        return self._cover_image_data
