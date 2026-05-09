# Prototype results

Empirical data from running [`prototype.py`](prototype.py),
[`probe.py`](probe.py), and [`cmyk_probe.py`](cmyk_probe.py) against
14 PDFs in `/Users/aj/Milliways/Comics/full/` on Apple Silicon
with PyMuPDF via `comicbox-pdffile` 0.5+.

Test corpus is intentionally diverse: image-comic scans, vector text
PDFs, mixed scripts/comics, OCR overlays, and the PDF 2.0 spec
example files.

## Per-PDF detector verdict (first 12 pages)

| PDF | pages | image-dominant | det p50 | det max | image format(s) |
|---|---:|---:|---:|---:|---|
| `dos-world-#19.pdf` (scanned mag, OCR-overlay) | 92 | 0/12 | 9.99 ms | 12.24 ms | jpeg (rejected: visible text) |
| `double-text.pdf` (multi-image, vector text) | 1 | 0/1 | 24.48 ms | 24.48 ms | jpeg+png (rejected: 4 images) |
| `#thaistory.pdf` (vector layout w/ insets) | 228 | 0/12 | 3.54 ms | 7.69 ms | jpeg+png (rejected: low coverage) |
| `Amphigorey.pdf` (comic) | 204 | **6/12** | 0.65 ms | 2.08 ms | png |
| `Nolo Press 8 Ways to Avoid Probate.pdf` | 249 | **2/12** (cover scan) | 3.01 ms | 5.37 ms | jpeg (page 1: CMYK) |
| `Nolo Press Working for Yourself.pdf` | 382 | 0/12 | 4.84 ms | 7.02 ms | png+jpeg (rejected: heavy text) |
| `Watchmen Comic Original Script.pdf` | 6 | **6/6** | 0.58 ms | 1.88 ms | jpeg |
| 7 × pdf20examples (spec test files) | 9 total | 0/9 | 0.58 ms | 4.97 ms | png+jpeg (rejected: low coverage / no images) |

Combined: **14 of 79 sampled pages classified as image-dominant**, all
correctly. Zero false positives observed.

## Within-document granularity

The most-validated finding: **the detector distinguishes within a
single PDF.**

`Nolo Press 8 Ways to Avoid Probate.pdf`:

```
page  dom?  imgs  cov%  text
   0     Y     1   100     0       ← scanned cover
   1     Y     1   100     0       ← scanned inside cover (CMYK)
   2     n     0     0  1514       ← vector text
   3     n     1     9  1488       ← vector text + small inset
   4     n     0     0  1579       ← vector text
   ...
```

Pages 0–1 use the IMAGE path; pages 2+ correctly fall through to PDF
rendering. This is the case the user explicitly raised: "people use
codex to display regular PDFs as well." The detector handles
mixed-content PDFs without per-comic configuration.

`Amphigorey.pdf`:

```
page  dom?  imgs  cov%
   0     Y     1    93     ← comic page
   1     n     1    41     ← title page (small image, lots of margin)
   2     n     1    60     ← chapter intro
   3     n     1    29     ← chapter intro
   4     n     1     1     ← mostly blank
   ...
   7     Y     1    95     ← comic page
   8     Y     1    92     ← comic page
```

Title pages and chapter intros correctly fall through to PDF
rendering even though they contain a single image — coverage is too
low.

## Image format diversity

```
dos-world-#19.pdf:                    jpeg=8 colorspaces=RGB
double-text.pdf:                      jpeg=1, png=3
#thaistory.pdf:                       jpeg=1, png=3
Amphigorey.pdf:                       png=8 (all grayscale)
Nolo Press 8 Ways to Avoid Probate:   jpeg=3 (RGB, CMYK, Gray) ⚠
Nolo Press Working for Yourself:      png=7, jpeg=2
Watchmen Comic Original Script:       jpeg=6 (RGB)
PDF 2.0 image with BPC.pdf:           jpeg=2
PDF 2.0 with page level output intent: png=2
pdf20-utf8-test:                      png=1
```

**No JBIG2, JPEG2000, CCITT, or TIFF** in this corpus. The transcode
fallback for those formats is defensive code that won't fire here,
but stays in the design for future-proofing.

**One CMYK image found** (Nolo Press 8 Ways page 1, jpeg cs=4). The
transcode path handles it correctly:

```
ext   cs  mode             tx_ms safe?   sz_dir    sz_tx
jpeg   4  rgb-transcode    19.77     Y   118759    95964
```

PIL decodes the transcoded bytes as `RGB` mode → browser-safe.

## Performance

Detector overhead per page (cold, no caching):

```
median across all PDFs:    1.1 ms
p99 across all PDFs:      12.2 ms (dos-world-#19, page 2: 4855 chars)
worst-case (multi-image, lots of text): 24.5 ms (double-text.pdf)
```

For comparison, the operations the detector is trying to *avoid*:

```
get_page_pixmap + JPEG encode (page render):  10–95 ms
convert_to_pdf (current default for PDFs):    5–20 ms
```

The detector is cheaper than even the cheapest current path. After
caching the verdict on `_ArchiveEntry`, subsequent requests pay zero
detection cost.

## Output sizes

For matched pages, raw extracted bytes are typically **smaller** than
the equivalent single-page PDF (which wraps the same JPEG + PDF
overhead):

```
Amphigorey p7:   ext=417 KB,  pdf=427 KB,  pix=63 KB (lossy)
Watchmen  p0:   ext=516 KB,  pdf=518 KB,  pix=224 KB (lossy)
Nolo p0:        ext=52 KB,   pdf=55 KB,   pix=65 KB
```

`pix` (full-page rasterize) is smaller because PyMuPDF re-encodes at
default quality; not directly comparable.

Bandwidth equivalence is a non-event: matched pages are the same
size as today's PDF responses, ±5%.

## Edge cases identified

### Visible OCR text on scanned PDFs

`dos-world-#19.pdf` is a scan with OCR rendered visibly (mode 0,
font `HiddenHorzOCR`). Coverage is 100% but `get_text("text")`
returns 200–5000 chars per page. The detector rejects these pages,
correctly — the visible OCR text *is* part of the rendered page,
even if it overlaps the raster.

These pages keep the existing `?hide_text=1` workaround on the PDF
fallback path. Future refinement: detect mode-0 text rendered with a
known invisible-font name (`HiddenHorzOCR` family) and treat as
invisible. Not in scope for v1.

### Multi-image pages

`double-text.pdf` has 4 images (JPEG raster + 3 tiny PNGs presumably
for icons/overlays). `extract_image` would return only one. Detector
rejects via `n_images != 1` → PDF fallback. Correct.

A future refinement could detect "1 dominant + N tiny" and ignore
sub-1% bbox satellites; not required for v1.

### CMYK colorspace

Nolo Press 8 Ways page 1 has a CMYK JPEG. Pure `extract_image` would
return CMYK bytes that Chrome renders with wrong colors. The
transcode path through `Pixmap(csRGB, pix).tobytes("jpeg")` produces
a 96 KB RGB JPEG that PIL verifies decodes to mode `RGB`.
**Verified working.**

### Rotation

No rotated pages in test corpus. Defensive design: `page.rotation != 0`
downgrades to `IMAGE_TRANSCODE` (Pixmap respects rotation flags).
Worth adding to the fixture set for the test suite.

## Threshold validation

The `MIN_COVERAGE = 0.85` threshold is well-clear of both classes:

- Image-dominant pages: 92, 93, 94, 95, 100% — all comfortably above 85%.
- Non-dominant pages: 1, 2, 7, 19, 29, 39, 41, 50, 51, 59, 60, 63, 68% — all comfortably below.

No page in the corpus sits in the 70–84% zone. The threshold could
move to 0.80 or 0.90 without changing any verdict in this dataset.
Defaulting to 0.85 is a defensible middle.

The `MAX_TEXT_CHARS = 50` threshold is similarly safe:

- Image-dominant pages: 0 chars (most), 0 chars, 0 chars …
- Non-dominant pages: 117, 199, 275, 276, 357, 390, 514, 669, 742, 857 …

Big gap between classes. The actual edge case is "scanned page with
OCR overlay" (`dos-world`) where text count is 100s–1000s and the
detector correctly rejects.

## What this validates

- Detector correctness: 100% on the test corpus. Zero false positives,
  zero false negatives that would cause user-visible quality loss.
- Performance: detector runs in <13 ms p99 cold; <1 ms hot. Negligible
  next to current rendering.
- CMYK transcode: works, ~20 ms overhead, browser-safe output verified.
- JBIG2/JPEG2000 path: not exercised by corpus but defensive.

## What this does NOT validate

- **Rotated PDFs** — no fixtures. Add a synthetic `/Rotate 90` PDF
  to the test suite.
- **Annotations and form fields** — no fixtures. The vector-ink gate
  (`page.get_drawings()`) likely catches these but should be tested.
- **Encrypted PDFs** — not exercised. Existing
  `@password-requested` handler in [`pdf-doc.vue:14`](../../frontend/src/components/reader/pager/pdf-doc.vue:14)
  should still apply on the fallback path.
- **JBIG2 / JPEG2000 PDFs** — defensive code is sound, but worth a
  synthetic fixture before declaring this hardened.

## Reproducing

The exploratory scripts that produced these numbers
(`prototype.py`, `probe.py`, `cmyk_probe.py`, `integration_check.py`)
are not committed — they were one-off harnesses against a private
PDF corpus. The detection logic itself is now in
`codex/views/reader/_pdf_image_serve.py`; running it against a
local corpus is a few lines of glue around `classify_page` and
`extract_image_for_page`.
