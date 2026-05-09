# Implementation: file-by-file changes

Three layers of change, ordered by dependency.

## Layer 1: `comicbox-pdffile` (upstream, separate PR)

### Add a new `PageFormat` value and a classifier method

[`pdffile/__init__.py`](../../.venv/lib/python3.14/site-packages/pdffile/__init__.py)

```python
class PageFormat(Enum):
    PDF = "pdf"
    IMAGE = "image"
    PIXMAP = "pixmap"
    IMAGE_IF_DOMINANT = "image_if_dominant"  # NEW
```

Add a public classifier on `PDFFile`:

```python
def classify_page(self, index: int) -> PageVerdict:
    """Return verdict for whether page can be served as a raw image."""
```

…and route `read()` for the new format mode through the classifier
plus extraction. Returns `None` (or raises a sentinel) when the page
isn't image-dominant, so the caller falls back to PDF format.

### Why upstream

The classifier needs PyMuPDF APIs (`get_image_bbox`, `extract_image`,
`Pixmap`) that `pdffile` already imports. Putting it in `pdffile`
keeps codex free of a direct PyMuPDF dependency — same separation
that exists today.

### Compatibility

`comicbox~=3.0.0` already passes through `pdf_format` and `hide_text`
kwargs unchanged. The new format value rides the same plumbing. Bump
the `pdffile` minor version (0.5 → 0.6); pin codex's
`comicbox[pdf]` to the new minimum.

## Layer 2: codex backend

### `codex/views/reader/_archive_cache.py`

Cache the verdict on the archive entry:

```python
class _ArchiveEntry:
    __slots__ = ("comicbox", "last_access", "lock", "path", "verdicts")

    def __init__(self, path: str, comicbox: Comicbox, last_access: float) -> None:
        # … existing fields …
        self.verdicts: dict[int, object] = {}
```

No other changes to the cache; the existing per-archive lock
serializes verdict reads/writes.

### `codex/views/reader/page.py`

Replace [`_get_page_image`](../../codex/views/reader/page.py:79-127)
with verdict-driven dispatch:

```python
_PDF_MIME = "application/pdf"
_FORMAT_HINTS = frozenset({"auto", "pdf", "image"})


def _get_page_image(self) -> tuple[bytes, str]:
    pk = self.kwargs.get("pk")
    path, file_type = self._resolve_path_and_type(pk)
    page = self.kwargs.get("page")

    fmt_hint = self.request.GET.get("format", "auto").lower()
    if fmt_hint not in _FORMAT_HINTS:
        fmt_hint = "auto"
    hide_text = self.request.GET.get("hide_text", "").lower() not in FALSY

    is_pdf = file_type == FileTypeChoices.PDF.value

    with archive_cache.open(path) as cb:
        # Fast path: image-dominant detection for PDFs only.
        if is_pdf and fmt_hint != "pdf":
            blob, content_type = self._try_image_serve(cb, page, fmt_hint)
            if blob is not None:
                return blob, content_type

        # Fallback: original path.
        if is_pdf:
            blob = cb.get_page_by_index(page, pdf_format="", hide_text=hide_text)
            return blob or b"", _PDF_MIME
        # Non-PDF archive — unchanged.
        blob = cb.get_page_by_index(page)
        return blob or b"", self.content_type
```

`_try_image_serve` (new private helper):

```python
def _try_image_serve(self, cb, page, fmt_hint):
    """Return (bytes, content_type) or (None, None) if not viable."""
    if fmt_hint == "image":
        # Force pixmap path — always works, may be slower.
        blob = cb.get_page_by_index(page, pdf_format="pixmap")
        return blob, "image/jpeg"  # pdffile pixmap is PPM today; see note
    blob, ext = cb.get_page_by_index(page, pdf_format="image_if_dominant")
    if blob is None:
        return None, None
    return blob, f"image/{ext}"
```

Open question: **`pdffile.read_pixmap` returns PPM bytes today.**
Either `pdffile` adds a JPEG-encoded pixmap output (preferred — see
[1-detector.md](01-detector.md)), or codex pipes the PPM through
PIL like the cover generator does. Suggested: bake JPEG output
into `pdffile` so codex stays a thin caller.

### Drop the latent `?pixmap=` parameter

[page.py:86-90](../../codex/views/reader/page.py:86) — the existing
`?pixmap=1` returns PPM bytes labeled `image/jpeg`. No frontend caller
exists. Replaced by `?format=image` with proper content-type.

### OpenAPI schema

Replace the `pixmap` parameter with `format`:

```python
@extend_schema(
    parameters=[
        OpenApiParameter("bookmark", OpenApiTypes.BOOL, default=True),
        OpenApiParameter("format", OpenApiTypes.STR, default="auto",
                         enum=["auto", "pdf", "image"]),
        OpenApiParameter("hide_text", OpenApiTypes.BOOL, default=False),
    ],
    responses={
        (200, "image/jpeg"): OpenApiTypes.BINARY,
        (200, "image/png"): OpenApiTypes.BINARY,
        (200, _PDF_MIME): OpenApiTypes.BINARY,
    },
)
```

### Tests

Add fixtures (commit small synthetic PDFs to `codex/tests/fixtures/pdf/`):

- `image_dominant_jpeg.pdf` — single full-bleed JPEG, no text.
- `image_dominant_cmyk.pdf` — single full-bleed CMYK JPEG.
- `vector_text.pdf` — vector-rendered text, no images.
- `mixed.pdf` — image + significant text.
- `multi_image.pdf` — multiple images on one page.
- `rotated.pdf` — image-dominant with `/Rotate 90`.

Test cases:

1. Each fixture returns the expected content-type via the page endpoint.
2. `?format=pdf` always returns `application/pdf`.
3. `?format=image` always returns `image/*`.
4. `?hide_text=1` is honoured when the page falls back to PDF.
5. Detector cache: requesting page 0 twice on the same archive runs
   the detector exactly once (instrument via patch).

## Layer 3: codex frontend

### Drop full-PDF mode

[`pager.vue`](../../frontend/src/components/reader/pager/pager.vue):

```diff
- import PagerHorizontal from "@/components/reader/pager/pager-horizontal.vue";
- const PagerPDF = markRaw(
-   defineAsyncComponent(
-     () => import("@/components/reader/pager/pager-full-pdf.vue"),
-   ),
- );
- import PagerVertical from "@/components/reader/pager/pager-vertical.vue";
+ import PagerHorizontal from "@/components/reader/pager/pager-horizontal.vue";
+ import PagerVertical from "@/components/reader/pager/pager-vertical.vue";
```

Remove the `readerFullPdf` computed and the `cacheBook` exclusion in
[reader.js:170-180](../../frontend/src/stores/reader.js):

```diff
- cacheBook() {
-   return (
-     this.activeSettings.cacheBook &&
-     !(this.isPDF && this.activeSettings.isVertical)
-   );
- },
+ cacheBook() {
+   return this.activeSettings.cacheBook;
+ },
```

### Drive component choice from response, not `fileType`

[`page.vue:106-108`](../../frontend/src/components/reader/pager/page/page.vue:106):

The simplest robust shape is to **always start with `<ImgPage>`** and
fall back to `<PDFDoc>` on a load error. The browser auto-detects from
content-type when the response is a PDF — `<img src=…>` will fail
to render, fire `error`, we re-mount as `<PDFDoc>` with `?format=pdf`
appended.

```vue
<template>
  <ImgPage v-if="!fallbackToPDF" ... @error="onImgError" />
  <PDFDoc v-else ... :src="srcWithFormatPdf" />
</template>
```

```javascript
data() {
  return { fallbackToPDF: false, ... };
},
methods: {
  onImgError(event) {
    if (this.book.fileType === "PDF" && !this.fallbackToPDF) {
      this.fallbackToPDF = true;  // re-mount as PDFDoc
      return;
    }
    this.error = "load";  // existing path
  },
},
```

For non-PDF books (`fileType !== "PDF"`), `onImgError` keeps the
existing behaviour. For PDFs, the first load attempt is `<img>`; if
the server returned `application/pdf` (i.e. `PDF_FALLBACK`), the
browser fails the image load and we swap in `<PDFDoc>`.

This avoids a HEAD request to determine content-type, and avoids
threading the verdict through the API response.

### Delete dead files

- `frontend/src/components/reader/pager/pager-full-pdf.vue`
- `frontend/src/components/reader/pager/pdf-doc.vue` — keep only if
  the fallback path still uses it; otherwise delete and inline a
  thin wrapper. Decision: **keep** — the fallback path uses it.
- `frontend/src/api/v3/reader.js` `getPDFInBrowserURL` export:
  delete unless the download panel still uses it (check
  `download-panel.vue`).

### UI override toggle

Add to the reader settings drawer
([reader-drawer-settings](../../frontend/src/components/reader/drawer/)):

```vue
<v-select
  v-if="isPDF"
  v-model="pdfRenderMode"
  :items="[
    { value: 'auto', title: 'Automatic' },
    { value: 'image', title: 'Force image' },
    { value: 'pdf', title: 'Force vector' },
  ]"
  label="PDF rendering"
/>
```

Wire `pdfRenderMode` into [`getComicPageSource`](../../frontend/src/api/v3/reader.js)
as a `format=` query param.

Default: `auto`. Persist per-comic in the existing reader-settings
endpoint, alongside `fitTo` etc.

### Bundle size

`vue-pdf-embed` stays in `package.json` because the fallback path
uses it. The win is that for image-dominant comic PDFs, pdf.js never
loads — the `defineAsyncComponent` import in [pager.vue:18-22](../../frontend/src/components/reader/pager/pager.vue:18)
fires only when a fallback page actually mounts.

## Order of work

1. **Spike (codex-internal):** add the detector as a private helper
   in `codex/views/reader/page.py`, importing `pymupdf` directly.
   Wire `?format=auto|pdf|image` and the new content-type branches.
   Validate end-to-end against the Watchmen / Amphigorey / Nolo Press
   PDFs.
2. **Frontend swap:** implement the `<img>`-first fallback-to-`<PDFDoc>`
   shape. Delete `PagerFullPDF` and the `readerFullPdf` getter.
3. **UI toggle:** add the per-comic override to reader settings.
4. **Upstream pdffile:** lift the detector and JPEG-pixmap output
   into `pdffile`, replace the codex-internal `pymupdf` import with
   `comicbox`-mediated calls.
5. **Tests + docs:** fixtures, integration tests, README/changelog.

Steps 1–3 can ship as one PR (codex-only, no upstream blocker).
Step 4 is a follow-up PR after the upstream `pdffile` release.
