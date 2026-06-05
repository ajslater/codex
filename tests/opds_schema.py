"""
Validate Codex OPDS feeds against the official specs.

Consumed by ``tests/test_opds_schema.py``. The schema files live under
``tests/schema/opds/`` (vendored verbatim — see that directory's README).

* **OPDS 2.0** (JSON) — every vendored ``*.json`` is loaded into a
  ``referencing.Registry`` keyed by its ``$id`` so the cross-repo ``$ref`` graph
  (OPDS → Readium webpub-manifest) resolves offline. Validated with
  ``jsonschema`` (draft-07).
* **OPDS 1.2** (Atom XML) — ``opds.rnc`` (which ``include``s ``atom.rnc``) is read
  with ``rnc2rng``, compiled to RELAX NG, and run via ``lxml``.

Each ``validate_*`` helper returns a list of human-readable error strings — an
empty list means the document is schema-compliant.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import rnc2rng
from jsonschema import Draft7Validator
from lxml import (
    etree,  # ty: ignore[unresolved-import] # pyright: ignore[reportAttributeAccessIssue]
)
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

if TYPE_CHECKING:
    from collections.abc import Iterator

_SCHEMA_DIR = Path(__file__).parent / "schema" / "opds"
_V2_DIR = _SCHEMA_DIR / "v2"
_V1_DIR = _SCHEMA_DIR / "v1"

_FEED_SCHEMA_ID = "https://drafts.opds.io/schema/feed.schema.json"
_MANIFEST_SCHEMA_ID = (
    "https://readium.org/webpub-manifest/schema/publication.schema.json"
)
_AUTH_SCHEMA_ID = "https://drafts.opds.io/schema/authentication.schema.json"
_PROGRESSION_SCHEMA_ID = "https://drafts.opds.io/schema/progression.schema.json"

# Readium's link.schema.json refs the OPDS properties schema under
# ``specs.opds.io`` while the OPDS files declare ``$id`` under ``drafts.opds.io``.
# Register every OPDS schema under both hosts so either ref resolves.
_OPDS_HOST = "drafts.opds.io"
_OPDS_HOST_ALIAS = "specs.opds.io"


#############
# OPDS 2.0  #
#############


# JSON Schema ``pattern`` is ECMA-262 (JS) regex, but jsonschema compiles it
# with Python ``re``. The Readium schemas' BCP-47 language-tag pattern uses JS
# named groups ``(?<name>`` (and JS would write backrefs ``\k<name>``) which
# Python ``re`` can't parse. Rewrite to Python syntax — a pure dialect
# translation; the set of matched strings is unchanged. The ``[A-Za-z_]`` guard
# leaves lookbehind (``(?<=`` / ``(?<!``) alone.
_JS_NAMED_GROUP = re.compile(r"\(\?<([A-Za-z_])")
_JS_BACKREF = re.compile(r"\\k<([A-Za-z_][A-Za-z0-9_]*)>")


def _pythonize_patterns(node: Any) -> None:
    """Recursively rewrite JS-only ``pattern`` regexes to Python ``re`` syntax."""
    if isinstance(node, dict):
        pattern = node.get("pattern")
        if isinstance(pattern, str):
            node["pattern"] = _JS_BACKREF.sub(
                r"(?P=\1)", _JS_NAMED_GROUP.sub(r"(?P<\1", pattern)
            )
        for value in node.values():
            _pythonize_patterns(value)
    elif isinstance(node, list):
        for item in node:
            _pythonize_patterns(item)


@lru_cache(maxsize=1)
def _v2_registry() -> Registry:
    """Build a referencing Registry from every vendored v2 JSON schema."""
    resources: list[tuple[str, Resource]] = []
    for path in sorted(_V2_DIR.rglob("*.json")):
        schema = json.loads(path.read_text())
        _pythonize_patterns(schema)
        contents = Resource.from_contents(schema, default_specification=DRAFT7)
        uri = contents.id()
        if uri is None:
            msg = f"vendored schema missing $id: {path}"
            raise ValueError(msg)
        resources.append((uri, contents))
        if _OPDS_HOST in uri:
            resources.append((uri.replace(_OPDS_HOST, _OPDS_HOST_ALIAS), contents))
    return Registry().with_resources(resources)


def _validate_v2(data: Any, schema_id: str) -> list[str]:
    """Validate ``data`` against the registered schema, return error strings."""
    registry = _v2_registry()
    validator = Draft7Validator(registry.contents(schema_id), registry=registry)
    return [
        f"{error.json_path}: {error.message}"  # ty: ignore[unresolved-attribute]
        for error in sorted(validator.iter_errors(data), key=str)
    ]


def validate_opds2_feed(data: Any) -> list[str]:
    """Return OPDS 2.0 feed schema violations (empty list = compliant)."""
    return _validate_v2(data, _FEED_SCHEMA_ID)


def validate_opds2_manifest(data: Any) -> list[str]:
    """Return Readium webpub-manifest (publication) schema violations."""
    return _validate_v2(data, _MANIFEST_SCHEMA_ID)


def validate_opds_authentication(data: Any) -> list[str]:
    """Return Authentication-for-OPDS-1.0 document violations."""
    return _validate_v2(data, _AUTH_SCHEMA_ID)


def validate_opds_progression(data: Any) -> list[str]:
    """Return OPDS Progression 1.0 document violations."""
    return _validate_v2(data, _PROGRESSION_SCHEMA_ID)


#############
# OPDS 1.2  #
#############

# ``rnc2rng`` can't parse a few constructs in ``opds.rnc``. These transforms
# make it parseable while preserving every *structural* check; the only thing
# dropped is the price/rel datatype-exclusion nuance, and Codex serves free
# comics (it never emits ``opds:price``). Applied to an in-memory copy so the
# vendored file stays pristine.
_RNC_PATCHES: tuple[tuple[str, str, int], ...] = (
    # data-except (``a - (b)``) is unsupported by rnc2rng -> permissive ``text``.
    (
        r"atomUriExceptOPDS\s*=\s*string\s*-\s*\([^)]*\)",
        "atomUriExceptOPDS = text",
        re.DOTALL,
    ),
    # ``atomUri = xsd:anyURI - xsd:string {pattern=…}`` -> what atom.rnc itself uses.
    (r"^\s*atomUri\s*=\s*xsd:anyURI\s*-.*$", "  atomUri = text", re.MULTILINE),
    # typed-value ``string "x"`` -> bare literal ``"x"``.
    (r'\bstring\s+(")', r"\1", 0),
)
# Inlining ``atom.rnc`` pulls in xhtml:/s: prefixes + xsd datatypes the OPDS top
# file never declared; rnc2rng's serializer asserts every prefix is declared.
_RNC_NS_PREAMBLE = (
    'namespace xhtml = "http://www.w3.org/1999/xhtml"\n'
    'namespace s = "http://www.ascc.net/xml/schematron"\n'
    'datatypes xsd = "http://www.w3.org/2001/XMLSchema-datatypes"\n'
)
# rnc2rng emits ``namespace local = ""`` as the illegal ``xmlns:local=""``. The
# ``local:*`` wildcards correctly compile to ``<nsName ns=""/>`` so the prefix
# decl is unused — strip it so lxml will parse the RNG.
_XMLNS_LOCAL_RE = re.compile(r'\s+xmlns:local=(""|\'\')')


def _patch_opds_rnc(raw: str) -> str:
    """Make ``opds.rnc`` parseable by rnc2rng without losing structural checks."""
    patched = raw
    for pattern, repl, flags in _RNC_PATCHES:
        patched = re.sub(pattern, repl, patched, flags=flags)
    return _RNC_NS_PREAMBLE + patched


@lru_cache(maxsize=1)
def _v1_relaxng() -> etree.RelaxNG:
    """Compile the OPDS 1.2 RELAX NG schema (rnc -> rng -> lxml), cached."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # atom.rnc must sit beside the patched opds.rnc so ``include`` resolves
        # relative to the file (rnc2rng.load resolves against the file's dir).
        shutil.copy(_V1_DIR / "atom.rnc", tmp_dir / "atom.rnc")
        (tmp_dir / "opds.rnc").write_text(
            _patch_opds_rnc((_V1_DIR / "opds.rnc").read_text())
        )
        rng = rnc2rng.dumps(rnc2rng.load(str(tmp_dir / "opds.rnc")))
    rng = _XMLNS_LOCAL_RE.sub("", rng)
    return etree.RelaxNG(etree.fromstring(rng.encode()))


def validate_opds1(xml: bytes) -> list[str]:
    """Return OPDS 1.2 (Atom) RELAX NG violations (empty list = compliant)."""
    schema = _v1_relaxng()
    try:
        doc = etree.fromstring(xml)
    except etree.XMLSyntaxError as exc:
        return [f"XML parse error: {exc}"]
    if schema.validate(doc):
        return []
    return [str(error) for error in schema.error_log]


###############################
# OPDS Page Streaming (PSE) 1.2 #
###############################

_ATOM_NS = "http://www.w3.org/2005/Atom"
_PSE_STREAM_REL = "http://vaemendis.net/opds-pse/stream"


@lru_cache(maxsize=1)
def _pse_relaxng() -> etree.RelaxNG:
    """Compile the hand-authored OPDS-PSE 1.2 link RELAX NG, cached."""
    rng = rnc2rng.dumps(rnc2rng.load(str(_V1_DIR / "opds-pse-1.2.rnc")))
    rng = _XMLNS_LOCAL_RE.sub("", rng)
    return etree.RelaxNG(etree.fromstring(rng.encode()))


def validate_opds_pse(xml: bytes) -> list[str]:
    """
    Validate every OPDS-PSE page-streaming link in an Atom feed.

    Empty list = compliant (a feed with no PSE links is trivially compliant).
    """
    schema = _pse_relaxng()
    try:
        doc = etree.fromstring(xml)
    except etree.XMLSyntaxError as exc:
        return [f"XML parse error: {exc}"]
    errors: list[str] = []
    for link in doc.iterfind(f".//{{{_ATOM_NS}}}link[@rel='{_PSE_STREAM_REL}']"):
        # Re-parse the element standalone so it carries its own ns decls.
        element = etree.fromstring(etree.tostring(link))
        if not schema.validate(element):
            errors += [str(error) for error in schema.error_log]
    return errors


#################
# OpenSearch 1.1 #
#################


@lru_cache(maxsize=1)
def _opensearch_relaxng() -> etree.RelaxNG:
    """Compile the hand-authored OpenSearch 1.1 RELAX NG, cached."""
    rng = rnc2rng.dumps(rnc2rng.load(str(_V1_DIR / "opensearch-1.1.rnc")))
    rng = _XMLNS_LOCAL_RE.sub("", rng)
    return etree.RelaxNG(etree.fromstring(rng.encode()))


def validate_opensearch(xml: bytes) -> list[str]:
    """Return OpenSearch 1.1 description-document violations (empty = compliant)."""
    schema = _opensearch_relaxng()
    try:
        doc = etree.fromstring(xml)
    except etree.XMLSyntaxError as exc:
        return [f"XML parse error: {exc}"]
    if schema.validate(doc):
        return []
    return [str(error) for error in schema.error_log]


#######################################
# Profiles without an official schema #
#######################################

_DIVINA_PROFILE = "https://readium.org/webpub-manifest/profiles/divina"
_AUTH_DOC_TYPE = "application/opds-authentication+json"


def validate_divina_profile(manifest: Any) -> list[str]:
    """
    Lightweight DiViNa profile checks on top of the base webpub schema.

    https://github.com/readium/webpub-manifest/blob/master/profiles/divina.md
    The profile has no JSON schema; this asserts the two rules that matter for a
    comic manifest: it declares the profile, and its reading order is all images.
    """
    errors: list[str] = []
    metadata = manifest.get("metadata", {}) if isinstance(manifest, dict) else {}
    conforms = metadata.get("conformsTo")
    conforms_list = conforms if isinstance(conforms, list) else [conforms]
    if _DIVINA_PROFILE not in conforms_list:
        errors.append("metadata.conformsTo is missing the DiViNa profile")
    reading_order = manifest.get("readingOrder") or []
    if not reading_order:
        errors.append("readingOrder is empty")
    for index, item in enumerate(reading_order):
        media_type = item.get("type", "") if isinstance(item, dict) else ""
        if not media_type.startswith("image/"):
            errors.append(f"readingOrder[{index}].type {media_type!r} is not an image")
    return errors


def _iter_authenticate(node: Any) -> Iterator[Any]:
    """Yield every link-properties ``authenticate`` value in a feed."""
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict) and "authenticate" in properties:
            yield properties["authenticate"]
        for value in node.values():
            yield from _iter_authenticate(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_authenticate(item)


def validate_v2_authenticate(feed: Any) -> list[str]:
    """
    Lightweight check of the OPDS 2.0 link ``authenticate`` property.

    Proposed in https://github.com/opds-community/drafts/discussions/43 (no
    formal schema): a gated link carries an ``authenticate`` pointer to the OPDS
    Authentication Document. Assert each is a link to that document.
    """
    errors: list[str] = []
    for auth in _iter_authenticate(feed):
        if not isinstance(auth, dict) or not auth.get("href"):
            errors.append(f"authenticate is not a link with href: {auth!r}")
        elif auth.get("type") != _AUTH_DOC_TYPE:
            errors.append(
                f"authenticate.type {auth.get('type')!r} != {_AUTH_DOC_TYPE!r}"
            )
    return errors
