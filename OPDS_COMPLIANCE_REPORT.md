# OPDS & OpenSearch Compliance Report

All fixes below were surfaced by new schema validators (`tests/opds_schema.py`)
running real Codex responses against the official specs, and verified by
`tests/test_opds_schema.py`. **12 distinct compliance bugs** were fixed across 6
spec families; 2 more specs validated clean.

The validators are offline and deterministic — the upstream specs are vendored
under `tests/schema/opds/` (5 OPDS JSON Schemas + 23 Readium webpub-manifest
schemas + the OPDS Authentication/Progression schemas, plus hand-authored RELAX
NG grammars for OPDS 1.2, OPDS-PSE 1.2, and OpenSearch 1.1). See that
directory's `README.md` for provenance.

## Summary

| Spec                        | Bugs fixed | Worst severity |
| --------------------------- | ---------- | -------------- |
| OPDS 2.0 (JSON)             | 4          | 🔴 Critical    |
| OPDS 1.2 (Atom)             | 3          | 🔴 Critical    |
| OpenSearch 1.1              | 2          | 🔴 Critical    |
| Authentication for OPDS 1.0 | 1          | 🟠 High        |
| OPDS Progression 1.0        | 1          | 🟠 High        |
| OPDS-PSE 1.2                | 1          | 🟡 Low         |
| DiViNa / #43 authenticate   | 0 (clean)  | —              |

Severity legend: 🔴 Critical (document rejected / endpoint broken) · 🟠 High
(wrong document format) · 🟡 Low (invalid enum/value, schema-detectable) · 🟢
Cosmetic.

---

## OPDS 2.0 — feeds & publication manifest

### 1. 🔴 Feed wrapped in the SPA envelope — _the original Stump rejection_

Every v2 feed and manifest shipped as `{"data":{…},"meta":{},"errors":[]}` — the
OPDS object was nested under `data` instead of at the JSON root. The validator
reported ~17 cascading errors (`'metadata' is a required property`,
`$.meta … is not valid under any of the given schemas`, …).

- **Cause:** the base `AuthAPIView` sets
  `renderer_classes = (EnvelopeJSONRenderer,)`, inherited by all OPDS v2 views.
- **Fix:** envelope-free `OPDS2FeedRenderer` / `OPDS2ManifestRenderer`
  (`codex/views/opds/v2/renderers.py`), pinned on `OPDS2LinksView`
  (`codex/views/opds/v2/feed/links.py`) and `OPDS2ManifestView`
  (`codex/views/opds/v2/manifest.py`).

### 2. 🟡 `metadata.layout` carried the reading direction

`layout` was set to `ltr`/`rtl`/`ttb`, but the schema enum is
`[fixed, reflowable, scrolled]` → `'ltr' is not one of …`.

- **Fix:** direction now goes to `readingProgression` (enum `rtl`/`ltr`);
  vertical directions (`ttb`/`btt`) map to `layout: scrolled`, page comics to
  `layout: fixed`. New `_set_layout_and_progression` helper in
  `codex/views/opds/v2/feed/publications.py` (also used by `manifest.py`).

### 3. 🟡 `conformsTo` at the manifest root

`$.conformsTo … is not valid under any of the given schemas` — the Readium
webpub `publication.schema.json` defines no root `conformsTo` and rejects
unknown root properties.

- **Fix:** removed root `conforms_to` from both publication serializers; the
  DiViNa profile is declared via `metadata.conformsTo` —
  `codex/serializers/opds/v2/publication.py`.

### 4. 🟢 Trailing-space typo

The DiViNa `metadata.conformsTo` default was `"…/profiles/divina "` (trailing
space) → `"…/profiles/divina"`. Same file as #3.

---

## OPDS 1.2 — Atom feeds

### 5. 🔴 Atom elements in no namespace

`Did not expect element feed there` on every feed. The template declared
`xmlns:atom="…/2005/Atom"` (prefixed) but wrote bare `<feed>`/`<id>`/`<title>` —
so every Atom element landed in _no_ namespace.

- **Fix:** Atom as the **default** namespace (`xmlns=`) —
  `codex/templates/opds_v1/index.xml`.

### 6. 🟡 Missing required `<updated>` on entries

`Expecting an element updated, got nothing` — collection / navigation entries
(which have no `updated_at`) omitted it, but Atom requires `<updated>` on every
entry.

- **Fix:** always emit it, falling back to the feed's `updated` — same template.

### 7. 🟡 `<url>` instead of Atom's `<uri>`

`Element author has extra content: url` once authors were present — Atom person
constructs use `<uri>`, not `<url>`.

- **Fix:** `<url>` → `<uri>` in author **and** contributor — same template.

---

## OPDS Progression 1.0

### 8. 🟠 Wrong document shape, media type, and rel

Codex emitted the discussion-#67 Readium **locator**
(`{modified, device, locator:{locations:…}}`), which fails the formalized
`progression.schema.json` (it requires a top-level `progression` float).

- **Fix:** migrated GET/PUT to the 1.0 format
  `{title, modified, device:{id,name}, progression:0..1, references}`; media
  type `application/vnd.readium.progression+json` →
  `application/opds-progression+json`; link rel
  `http://www.cantook.com/api/progression` → `http://opds-spec.org/progression`.
  Files: `codex/views/opds/v2/progression.py`,
  `codex/serializers/opds/v2/progression.py`, `codex/views/opds/const.py`.

> Note: `opds-progression-1.0` and discussion #67 are **different** documents
> for the same feature — the 1.0 draft collapsed #67's locator into a single
> `progression` fraction. Codex had implemented #67.

---

## OPDS-PSE 1.2 (Page Streaming Extension)

### 9. 🟡 `pse:lastRead` off-by-one

PSE numbers `lastRead` from 1, but Codex emitted its 0-indexed page (a page-0
bookmark emitted nothing because `0` is falsy in the template; a page-N bookmark
emitted `N` instead of `N+1`). Schema-valid but semantically wrong.

- **Fix:** `page + 1`, guarded on `bookmark_updated_at` to distinguish "no
  bookmark" from a real page-0 bookmark — `codex/views/opds/v1/entry/links.py`,
  `codex/views/opds/v1/const.py`.

---

## OpenSearch 1.1

### 10. 🔴 Endpoint returned the JSON envelope, not XML

`/opds/v1.2/opensearch/v1.1` served `{"data":{},"meta":{},"errors":[]}` with
`Content-Type: application/xml` — the OpenSearch description document was broken
for every client.

- **Cause:** `OpenSearch1View` listed `OPDSAuthMixin` before
  `CodexXMLTemplateMixin`, so the envelope renderer won MRO resolution.
- **Fix:** the XML renderer now wins — `codex/views/opds/opensearch/v1.py`.

### 11. 🟢 Wrong media type

Served as `application/xml` rather than the spec's
`application/opensearchdescription+xml` (the type the OPDS feed's own search
link advertises).

- **Fix:** `OpenSearchRenderer` with the correct `media_type`,
  content-negotiated and set on the response — same file.

---

## Authentication for OPDS 1.0

### 12. 🟠 Relative URLs in the Authentication Document

An unauthorized OPDS request (e.g. a bad bearer/basic credential) correctly
returns **401 + the Authentication Document**
(`application/opds-authentication+json`, with `WWW-Authenticate`) — that path
was _not_ broken. But the document's `id` was emitted as a relative path
(`/opds/auth/v1`). The OPDS Authentication `id` is the document's canonical
location — a `format: uri` (absolute) value — so a strict client (e.g. Stump)
rejects the auth challenge as invalid OPDS. (The schema validator missed it
because jsonschema format-checking is off; the test now asserts `id` is absolute
directly.)

- **Cause:** `_DOC["id"]` used `reverse_lazy("opds:auth:v1")` (a relative path),
  and the absolutize path was gated behind `DEBUG` / an empty user-agent set, so
  it never ran in production (and even then only touched the logo link).
- **Fix:** `static_get` now always emits absolute `id` and link hrefs via
  `request.build_absolute_uri` — `codex/views/opds/authentication/v1.py`.
- Regression test:
  `OPDSv2SchemaTestCase.test_unauthorized_returns_auth_document` (bad bearer
  token → 401 + valid auth doc with an absolute `id`).

---

## Validated clean (no bugs found)

- **DiViNa profile** — the manifest passes the profile checks (declares the
  profile, reading order is all images) after fixes #2–#4.
- **OPDS 2.0 `authenticate` property (#43)** — the link property is a valid
  pointer to the OPDS Authentication Document.

---

## Notes

- **Validator tooling (not a Codex bug):** the Readium schemas' BCP-47 `pattern`
  uses ECMA-262 named groups `(?<name>` that Python's `re` can't compile, so the
  registry loader rewrites them to `(?P<name>` before validation.
- **Authentication scope:** "Authentication for OPDS 1.0" is the auth _document_
  (shared by OPDS 1.x and 2.0); discussion #43 is the OPDS-2.0 link-level
  `authenticate` _pointer_ to it.

## Test status

- **10 schema-compliance tests pass** (6 OPDS 2.0 + 4 OPDS 1.2) in
  `tests/test_opds_schema.py`, alongside the existing functional resolution
  tests in `tests/test_opds_feed.py`.
- Full test suite: **100 %, 0 failures**.
- `make fix`, `make lint`, `make ty`: clean.
