#!/usr/bin/env python3
"""
Re-download the vendored OPDS / Readium / Atom schemas.

The OPDS test suite (``tests/test_opds_schema.py``) validates Codex's feeds
against the *official* specs offline. Those spec files are vendored next to this
script so CI never touches the network and the validation is deterministic. Run
this script to refresh them against newer upstream commits.

    python tests/schema/opds/fetch_schemas.py

Sources (pinned by commit SHA for reproducibility):

* OPDS 2.0 JSON Schema   — github.com/opds-community/specs       schema/*.json
* OPDS 1.2 RELAX NG (rnc) — github.com/opds-community/specs       schema/1.2/opds.rnc
* Readium webpub-manifest — github.com/readium/webpub-manifest    schema/**/*.json
  (OPDS 2.0 ``$ref``s into these)
* Atom RELAX NG (atom.rnc) — RFC 4287 App. B, via opengeospatial/schema-utils
  (``opds.rnc`` ``include``s it)

Vendored files are kept PRISTINE — the small transforms needed to make
``opds.rnc`` parseable by ``rnc2rng`` live in ``tests/opds_schema.py`` so the
diff against upstream stays empty and auditable.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

# Pinned upstream commits (refresh these to bump versions).
OPDS_SHA = "ff42456415876e9634f14e1fa4dad9a75721f802"
DRAFTS_SHA = "14026341d384d742aa4eadd5589295889ed807ed"
READIUM_SHA = "379522e248b2e3bf14a75caaa11370e033278d2e"
ATOM_SHA = "8d2a5dc7189758bdbb63263da5d43605497aade0"

RAW = "https://raw.githubusercontent.com"
OPDS_BASE = f"{RAW}/opds-community/specs/{OPDS_SHA}/schema"
DRAFTS_BASE = f"{RAW}/opds-community/drafts/{DRAFTS_SHA}/schema"
READIUM_BASE = f"{RAW}/readium/webpub-manifest/{READIUM_SHA}/schema"
ATOM_URL = (
    f"{RAW}/opengeospatial/schema-utils/{ATOM_SHA}/src/test/resources/relax/atom.rnc"
)

# OPDS 2.0 JSON Schemas (relative to OPDS_BASE).
OPDS_V2_FILES = (
    "feed.schema.json",
    "publication.schema.json",
    "feed-metadata.schema.json",
    "properties.schema.json",
    "acquisition-object.schema.json",
)

# Drafts with `$id` under drafts.opds.io (relative to DRAFTS_BASE). Shared across
# OPDS versions: the Authentication Document (Authentication for OPDS 1.0) and the
# OPDS Progression 1.0 document. Loaded into the same jsonschema registry.
DRAFTS_FILES = (
    "authentication.schema.json",
    "progression.schema.json",
)

# Readium webpub-manifest JSON Schemas (relative to READIUM_BASE). The OPDS 2.0
# schemas $ref into these; these in turn $ref each other.
READIUM_FILES = (
    "a11y.schema.json",
    "altIdentifier.schema.json",
    "article.schema.json",
    "chapter.schema.json",
    "collection.schema.json",
    "contributor.schema.json",
    "episode.schema.json",
    "extensions/encryption/properties.schema.json",
    "extensions/epub/metadata.schema.json",
    "extensions/epub/properties.schema.json",
    "extensions/epub/subcollections.schema.json",
    "issue.schema.json",
    "language-map.schema.json",
    "link.schema.json",
    "metadata.schema.json",
    "periodical.schema.json",
    "publication.schema.json",
    "season.schema.json",
    "series.schema.json",
    "storyArc.schema.json",
    "subcollection.schema.json",
    "subject.schema.json",
    "volume.schema.json",
)

HERE = Path(__file__).parent


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response:  # noqa: S310 - pinned https
        dest.write_bytes(response.read())
    print(f"  {dest.relative_to(HERE)}")


def main() -> None:
    """Download every vendored schema into place."""
    print("OPDS 2.0 schemas:")
    for name in OPDS_V2_FILES:
        _download(f"{OPDS_BASE}/{name}", HERE / "v2" / "opds" / name)

    print("OPDS drafts schemas (auth, progression):")
    for name in DRAFTS_FILES:
        _download(f"{DRAFTS_BASE}/{name}", HERE / "v2" / "opds" / name)

    print("Readium webpub-manifest schemas:")
    for name in READIUM_FILES:
        _download(f"{READIUM_BASE}/{name}", HERE / "v2" / "readium" / name)

    print("OPDS 1.2 + Atom RELAX NG:")
    _download(f"{OPDS_BASE}/1.2/opds.rnc", HERE / "v1" / "opds.rnc")
    _download(ATOM_URL, HERE / "v1" / "atom.rnc")


if __name__ == "__main__":
    main()
