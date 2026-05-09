# Detector: Image-Dominant Page Classification

## Inputs

`(doc: pymupdf.Document, index: int)` — already-open PyMuPDF document
and zero-based page index. The caller (`codex/views/reader/page.py`)
already has the document open via `archive_cache`.

## Output

```python
@dataclass(frozen=True, slots=True)
class PageVerdict:
    mode: Literal["IMAGE_DIRECT", "IMAGE_TRANSCODE", "PDF_FALLBACK"]
    image_xref: int | None       # which embedded image to extract, if any
    ext: str | None              # original encoding ("jpeg", "png", …)
    transcode_to: str | None     # "jpeg" if we must re-encode
```

## Detection algorithm

Three checks, all using PyMuPDF APIs that operate on parsed PDF
metadata (no rendering):

```python
def classify_page(doc, index) -> PageVerdict:
    page = doc.load_page(index)
    images = page.get_images(full=True)

    # Reject early on multi-image or zero-image pages.
    if len(images) != 1:
        return PageVerdict("PDF_FALLBACK", None, None, None)

    # Coverage: image bbox vs. page rect, clamped to 1.0.
    page_area = page.rect.width * page.rect.height
    bbox = page.get_image_bbox(images[0])
    coverage = (
        min((bbox.width * bbox.height) / page_area, 1.0)
        if page_area and not bbox.is_empty
        else 0.0
    )
    if coverage < MIN_COVERAGE:
        return PageVerdict("PDF_FALLBACK", None, None, None)

    # Visible-text gate: lots of visible text means the page has
    # vector-rendered content beyond the image.
    text_len = len(page.get_text("text").strip())
    if text_len > MAX_TEXT_CHARS:
        return PageVerdict("PDF_FALLBACK", None, None, None)

    # Vector-ink gate: any non-image drawings disqualify.
    if page.get_drawings():
        return PageVerdict("PDF_FALLBACK", None, None, None)

    # Rotation gate: skip extract_image when page is rotated; pixmap
    # path applies the rotation correctly.
    if page.rotation != 0:
        xref = images[0][0]
        return PageVerdict("IMAGE_TRANSCODE", xref, None, "jpeg")

    # All gates passed — decide direct vs. transcode based on the
    # embedded image's actual encoding and colorspace.
    xref = images[0][0]
    image_dict = doc.extract_image(xref)
    ext = (image_dict.get("ext") or "").lower()
    cs = image_dict.get("colorspace", 0)  # PyMuPDF reports n-channels

    if ext in BROWSER_NATIVE_EXTS and cs in BROWSER_NATIVE_COLORSPACES:
        return PageVerdict("IMAGE_DIRECT", xref, ext, None)
    return PageVerdict("IMAGE_TRANSCODE", xref, ext, "jpeg")
```

## Thresholds (initial values, validated against test corpus)

| Constant | Value | Rationale |
|---|---|---|
| `MIN_COVERAGE` | `0.85` | Tight enough to reject pages with surrounding margins (Amphigorey's title pages at 41–60% fall through). Loose enough that scanned pages with fullbleed bleed-rect imprecision still match (Watchmen: 100%, Amphigorey comic pages: 92–95%). |
| `MAX_TEXT_CHARS` | `50` | OCR scraps (page numbers, edge text) are typically <50 chars. Real text content (`#thaistory.pdf`: 357–3185 chars) is far above this. |
| `MAX_IMAGES` | `1` | Multi-image pages are usually panel-split scans; `extract_image` would lose all but the first. Pixmap fallback or PDF fallback handles them correctly. |
| `BROWSER_NATIVE_EXTS` | `{"jpeg", "jpg", "png", "webp"}` | Universal browser support. Excludes JBIG2 (none), JPEG2000 (Safari only), CCITT/TIFF (none). |
| `BROWSER_NATIVE_COLORSPACES` | `{1, 3}` | PyMuPDF's `colorspace` field is the n-channel count: 1 = Gray, 3 = RGB, 4 = CMYK. Browsers don't render CMYK JPEGs reliably. |

These are constants in code. **Do not** expose as env vars in the
first cut — telemetry from production use should drive any
tuning; ad-hoc env knobs make that signal noisier.

## Extraction

`IMAGE_DIRECT`:

```python
image_dict = doc.extract_image(xref)
return image_dict["image"], f"image/{image_dict['ext']}"
```

`IMAGE_TRANSCODE`:

```python
pix = pymupdf.Pixmap(doc, xref)
if pix.colorspace and pix.colorspace.n not in (1, 3):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)  # CMYK → RGB
blob = pix.tobytes("jpeg")
return blob, "image/jpeg"
```

Note: `Pixmap(doc, xref)` reads the embedded image — it does *not*
re-render the page. That's the cheap path. We only run
`page.get_pixmap()` (full page render) if `extract_image` itself
fails, which is rare.

## Performance budget

Measured against test corpus (Apple Silicon, PyMuPDF 1.x via
`pdffile` 0.5+):

| Operation | p50 | p99 |
|---|---|---|
| `classify_page` cold | 0.7 ms | 12 ms |
| `IMAGE_DIRECT` extract | 0.1 ms | 0.3 ms |
| `IMAGE_TRANSCODE` (CMYK 2400×3000) | 20 ms | — |
| `PDF_FALLBACK` (`convert_to_pdf`) | 5 ms | 20 ms |

Reference: `get_page_pixmap` (full-page render, used by cover thread)
is 50–300 ms on the same documents. The detector's worst case
(12 ms) is still less than the cheapest current rendering path.

## Caching the verdict

Add a `verdicts: dict[int, PageVerdict]` to each
`_ArchiveEntry` in [_archive_cache.py](../../codex/views/reader/_archive_cache.py).
Reset on archive close. No persistent cache — re-detecting on a cold
archive costs ~1 ms per page, paid once per LRU cycle.

```python
class _ArchiveEntry:
    __slots__ = ("comicbox", "last_access", "lock", "path", "verdicts")

    def __init__(self, path, comicbox, last_access):
        # … existing init …
        self.verdicts: dict[int, PageVerdict] = {}
```

The lock that already serializes extraction (per-archive
`threading.Lock`) covers the verdict cache too — no new
synchronization.

## Override semantics

Query parameter `?format=` on the page endpoint:

| Value | Behaviour |
|---|---|
| `auto` (default) | Run detector, use verdict |
| `pdf` | Skip detector, force `PDF_FALLBACK` |
| `image` | Skip detector, force `IMAGE_TRANSCODE` (always works, slower) |

`?hide_text=1` continues to apply only to `PDF_FALLBACK`. When the
detector matches `IMAGE_DIRECT`/`IMAGE_TRANSCODE`, the bytes are the
embedded raster; there's no "text layer" to hide.

## What the detector does NOT do

- **Render-mode-3 (invisible) text filtering.** The test corpus has
  no invisible-text PDFs (every OCR'd doc here uses mode 0 with
  `HiddenHorzOCR` font). Adding mode-3 awareness is a future
  refinement; for now visible OCR text correctly disqualifies a
  page.
- **Sample-based per-comic precomputation.** Per-page is fast
  enough that batch sampling at import time isn't worth the cache
  invalidation complexity.
- **Embedded annotation / form / link detection.** Pages with form
  fields or annotations should fall through to PDF rendering, but
  the existing `get_drawings()` check catches most of these
  (annotations are drawn as vector ink). If a regression appears,
  add a `len(page.annots()) == 0` gate.
