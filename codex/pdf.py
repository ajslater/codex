"""Mimic comicbox.ComicArchive functions for PDFs."""
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

from comicbox.metadata.filename import FilenameMetadata
from filetype import guess
from pdf2image import convert_from_path
from pdfrw import PdfReader, PdfWriter
from PIL import Image
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
        self._cover_pil_image: Optional[ImageType] = None

    def is_pdf(self):
        """Is the path a pdf."""
        kind = guess(self._path)
        return kind and kind.mime == self.MIME_TYPE

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

    def get_cover_pil_image(self) -> ImageType:
        """Get the first page as a image data."""
        if not self._cover_pil_image:
            pil_images = convert_from_path(
                self._path,
                first_page=self.COVER_PAGE_INDEX,
                last_page=self.COVER_PAGE_INDEX,
                thread_count=4,
                fmt="tiff",  # tiff fastest, maybe lossless.
                use_pdftocairo=True,
            )
            self._cover_pil_image = pil_images[0]
            print(self._cover_pil_image.format)
        return self._cover_pil_image

    @staticmethod
    def _to_pil_image(data: bytes) -> ImageType:
        return Image.open(BytesIO(data))
