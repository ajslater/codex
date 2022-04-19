import io

from pathlib import Path

from comicbox.metadata.filename import FilenameMetadata
from pdf2image import convert_from_path
from pdfrw import PdfReader, PdfWriter


class PDF:
    COVER_PAGE_INDEX = 1

    def __init__(self, path):
        self._path = Path(path)
        self._reader = None
        self._metadata = {}
        self._cover_image_data = None

    def _ensure_reader(self) -> None:
        if not self._reader:
            self._reader = PdfReader(self._path)

    def get_metadata(self) -> dict:
        if not self._metadata:
            self._ensure_reader()
            self._metadata = FilenameMetadata(
                path=self._path, string=self._path.name
            ).metadata
            self._metadata["page_count"] = self._reader.Root.Pages.Count
        return self._metadata

    def get_page_by_index(self, index):
        self._ensure_reader()
        page = self._reader.getPage(index)
        # stream = page.Contents.stream
        writer = PdfWriter()
        writer.addpage(page)
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def get_cover_image(self):
        if not self._cover_image_data:
            # TODO exceptions omg
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
            buffer = io.BytesIO()
            image.save(buffer, "JPEG")
            self._cover_image_data = buffer.getvalue()
        return self._cover_image_data
