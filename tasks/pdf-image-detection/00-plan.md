# PDF Reader: Image-Dominant Page Detection

## Goal

Most "comic PDFs" are scanned-image wrappers — one JPEG/PNG per page with
no real vector content. Today Codex routes every PDF page through the same
client-side `vue-pdf-embed` rendering pipeline, even when a `<img>` tag
would suffice. This plan adds a server-side detector that decides per page
whether the embedded image alone is enough, and serves that image
directly when it is. Pages that fail the detector keep the current
single-page-PDF + `vue-pdf-embed` path.

The end state: comic-style PDFs render through Codex's existing image
reader (same path as CBZ/CBR), and "real" multi-element PDFs keep
vector-quality rendering. The user can override per-page when the
detector misjudges.

## Why this is worth doing

1. **Most comic PDFs are image containers.** Empirically validated against
   a 14-PDF / ~100-page test corpus (see [99-prototype-results.md](99-prototype-results.md)):
   - `Watchmen Comic Original Script.pdf`: 6/6 pages image-dominant.
   - `Amphigorey.pdf`: comic pages match; title pages correctly fall through.
   - `Nolo Press 8 Ways to Avoid Probate`: scanned cover (pages 0–1)
     match; vector text body correctly falls through. **Within-document
     granularity works.**
   - `Nolo Press Working for Yourself`: 0/12 — pure vector text PDF.
     Correctly rejected.
2. **Browser-native rendering for matched pages.** No `<canvas>` /
   pdf.js worker / CSS sizing hacks. The `BookPage` component already
   renders `<img>` for CBZ/CBR; matched PDF pages join that path.
3. **The detector is essentially free.** p50 ≈ 1–5 ms per page,
   p99 ≈ 12 ms even on a 1 MB scanned page with an OCR text overlay.
   Tiny next to the existing extraction cost.
4. **No bandwidth regression.** Direct image bytes are roughly
   the same size as the corresponding single-page PDF (PDF wraps the
   same JPEG); often slightly smaller (no PDF object overhead).
5. **Side benefit for downloads.** The original "download original PDF"
   feature is unaffected.

## Decision summary

Hybrid path with three serving modes, decided per page:

| Verdict | Server output | Frontend | When |
|---|---|---|---|
| `IMAGE_DIRECT` | embedded JPEG/PNG bytes, content-type `image/{ext}` | `<img>` (existing `ImgPage`) | single image, ≥85% coverage, ≤50 visible chars, no vector ink, RGB/Gray colorspace |
| `IMAGE_TRANSCODE` | `Pixmap`-rendered RGB JPEG | `<img>` | as above but CMYK / non-browser-native source format (JBIG2, JPEG2000, CCITT) |
| `PDF_FALLBACK` | single-page PDF, content-type `application/pdf` | `vue-pdf-embed` (existing `PDFDoc`) | everything else |

Frontend chooses between `ImgPage` and `PDFDoc` from the response
content-type, not the comic's `fileType`. Override hook: `?format=pdf`
forces fallback even when the detector accepts.

## Things this plan does NOT change

- `comicbox` / `pdffile` stay the integration boundary. PyMuPDF stays
  out of `codex/` direct imports; the new detector is added to
  `pdffile` upstream.
- `archive_cache` and the per-archive `threading.Lock` model stay
  unchanged.
- Cover generation stays on its current path (already pixmap-based).
- Bookmark, ACL, prev/next prefetch — unchanged.
- The full-document `book.pdf` route stays as a download endpoint.
- The full-PDF reader mode (`PagerFullPDF`) is **removed** — see [02-implementation.md](02-implementation.md).
  It bypasses the detector and is the most fragile branch of the
  current code.

## What's new in this plan vs. the architectural report

The earlier report [scoped two options](../../README.md): keep current
(Option 1) or rasterize-everything (Option 3). This plan is the third
shape: **Option 3 when cheap, Option 1 when not.** It captures the
performance win without the quality regression on real vector PDFs.

The detector is the part that needed empirical validation. It now has
it (see prototype results); the rest of the plan is straightforward
glue.

## Subplan index

- [01-detector.md](01-detector.md) — detection logic, thresholds,
  classify-and-extract code.
- [02-implementation.md](02-implementation.md) — file-by-file changes
  in `pdffile`, `comicbox`, `codex/views/reader/page.py`, and the
  Vue reader.
- [99-prototype-results.md](99-prototype-results.md) — measurements
  from the test corpus, with edge cases identified.

## Out-of-scope follow-ups

- **DPR / hi-DPI image rendering for `IMAGE_TRANSCODE`.** The Pixmap
  fallback uses native page DPI (~72 DPI). For high-DPR displays
  reading vector PDFs, this would be soft. Realistic comic PDFs are
  scanned at ~150 DPI which is fine; revisit if anyone reports it.
- **Multi-image composition.** Pages with several panels stored as
  separate images currently fall through to `PDF_FALLBACK`. We could
  composite via Pixmap, but the fallback already handles them well.
- **OCR text overlay handling.** The existing `?hide_text=1` flag still
  applies; pages with visible OCR text fall through to `PDF_FALLBACK`
  where `hide_text` works as today.
- **Per-comic flag at import time.** Skipped intentionally — per-page
  detection is cheap and gives strictly better granularity. Revisit
  only if the page endpoint hot path proves bottlenecked on detection
  (telemetry says it won't).

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Detector false-positive renders unreadable image | Low | Medium | `?format=pdf` override; UI toggle in reader settings |
| CMYK transcode produces wrong colors | Low | Medium | Pixmap → DeviceRGB conversion verified in prototype against PIL decode |
| Multi-image page misclassified as single-image-dominant | Medium | Low | Detector counts all images; threshold `n_images <= 1` for IMAGE_DIRECT |
| Rotation handling breaks layout | Low (no rotated PDFs in test corpus) | Medium | If `page.rotation != 0`, downgrade to `IMAGE_TRANSCODE` (Pixmap respects rotation) |
| pdffile upstream change blocks codex release | Low | Medium | Implement detector in codex initially as a private helper that imports pymupdf directly; upstream as a follow-up PR |

## Acceptance criteria

1. The Watchmen scripts and Amphigorey comic pages render via `<img>`
   without `vue-pdf-embed` invoked.
2. The Nolo Press text PDFs render via `vue-pdf-embed` exactly as
   today.
3. Page-turn latency for image-dominant PDFs improves measurably (no
   pdf.js render on the client; image cache hit on the second pass).
4. Network panel shows `image/jpeg` (or `image/png`) for matched
   pages and `application/pdf` for fallback pages — no regression for
   either.
5. `?format=pdf` query parameter forces fallback for any PDF page.
6. Existing `?hide_text=1` continues to work for `PDF_FALLBACK` pages.
7. No new dependency added to `codex/`'s pyproject (pymupdf access
   remains via `comicbox[pdf]`).
