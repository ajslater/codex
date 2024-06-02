"""Clean metadata before importing."""

from contextlib import suppress
from decimal import ROUND_DOWN, Decimal
from typing import Any
from zipfile import BadZipFile

from comicbox.box import Comicbox
from comicbox.box.computed import IDENTIFIERS_KEY
from comicbox.exceptions import UnsupportedArchiveTypeError
from comicbox.schemas.comicbox_mixin import CONTRIBUTORS_KEY
from django.db.models import CharField
from django.db.models.fields import DecimalField, PositiveSmallIntegerField
from rarfile import BadRarFile

from codex.librarian.importer.const import FIS, STORY_ARCS_METADATA_KEY
from codex.librarian.importer.query_fks import QueryForeignKeysImporter
from codex.models import Comic
from codex.models.named import (
    ContributorPerson,
    ContributorRole,
    Identifier,
    IdentifierType,
    StoryArc,
)

_MD_INVALID_KEYS = frozenset(
    (
        "id",
        "created_at",
        "library",
        "parent_folder",
        "pk",
        "stat",
        "story_arc_number",
        "updated_at",
    )
)
_MD_VALID_KEYS = frozenset(
    (
        *(
            field.name
            for field in Comic._meta.get_fields()
            if field.name not in _MD_INVALID_KEYS
        ),
        "story_arcs",
    )
)
_MD_CHAR_KEYS = frozenset(
    field.name for field in Comic._meta.get_fields() if isinstance(field, CharField)
)
_MD_DECIMAL_KEYS = frozenset(
    field.name for field in Comic._meta.get_fields() if isinstance(field, DecimalField)
)
_MD_PSI_KEYS = frozenset(
    {
        field.name
        for field in Comic._meta.get_fields()
        if isinstance(field, PositiveSmallIntegerField)
    }
)
_PSI_MAX = 2**31 - 1
_SI_MIN = 2**15 * -1
_SI_MAX = 2**15 - 1
_DECIMAL_ZERO = Decimal("0.00")
_ALPHA_2_LEN = 2


class ExtractMetadataImporter(QueryForeignKeysImporter):
    """Clean metadata before importing."""

    @staticmethod
    def _title_to_name(md):
        """Convert title to name for comics."""
        with suppress(KeyError):
            md["name"] = md.pop("title")

    @staticmethod
    def _prune_extra_keys(dirty_md: dict[str, Any]) -> dict[str, Any]:
        """Remove unused keys."""
        allowed_md = {}
        for key in _MD_VALID_KEYS:
            val = dirty_md.get(key)
            if val is not None:
                allowed_md[key] = val
        return allowed_md

    @staticmethod
    def _assign_or_pop(md, key, value):
        if value is None:
            md.pop(key, None)
        else:
            md[key] = value

    @classmethod
    def _clean_decimal(cls, value, field_name: str):
        field: DecimalField = Comic._meta.get_field(field_name)  # type: ignore
        try:
            quantize_str = Decimal(f"1e-{field.decimal_places}")
            value = value.quantize(quantize_str, rounding=ROUND_DOWN)
            decimal_max = Decimal(10 ** (field.max_digits - 2) - 1)
            value = value.min(decimal_max)
        except Exception:
            value = None if field.null else _DECIMAL_ZERO
        return value

    @classmethod
    def _clean_comic_decimals(cls, md: dict[str, Any]) -> None:
        """Clean decimal values."""
        for key in _MD_DECIMAL_KEYS:
            value = md.get(key)
            if value is None:
                continue
            value = cls._clean_decimal(value, key)
            cls._assign_or_pop(md, key, value)

    @staticmethod
    def _clean_int(md, key, minimum, maximum):
        try:
            value = md.get(key)
            if value is not None:
                value = min(value, maximum)
                value = max(value, minimum)
        except Exception:
            field = Comic._meta.get_field(key)
            value = None if field.null else 0
        return value

    @classmethod
    def _clean_comic_positive_small_ints(
        cls,
        md: dict[str, Any],
    ) -> None:
        """Clean positive small integers."""
        for key in _MD_PSI_KEYS:
            value = cls._clean_int(md, key, 0, _PSI_MAX)
            cls._assign_or_pop(md, key, value)

    @classmethod
    def _clean_comic_small_ints(cls, md: dict[str, Any]):
        # clean sub value
        obj = md.get("volume", {})
        key = "name"
        value = cls._clean_int(obj, key, _SI_MIN, _SI_MAX)
        cls._assign_or_pop(obj, key, value)

    @staticmethod
    def _clean_charfield(model, field_name, value):
        try:
            field: CharField = model._meta.get_field(field_name)  # type: ignore
            if value:
                value = value[: field.max_length].strip()
            if not value:
                value = None
        except Exception:
            value = None
        return value

    @classmethod
    def _clean_charfields(cls, md: dict[str, Any]) -> None:
        for key in _MD_CHAR_KEYS:
            value = md.get(key)
            value = cls._clean_charfield(Comic, key, value)
            cls._assign_or_pop(md, key, value)

    @classmethod
    def _clean_pycountry(cls, md, key, lookup) -> None:
        try:
            value = md.get(key)
            if value and len(value) > _ALPHA_2_LEN and (obj := lookup.lookup(value)):
                value = obj.alpha_2
            if not value:
                value = None
        except Exception:
            value = None
        cls._assign_or_pop(md, key, value)

    @classmethod
    def _clean_contributors(cls, md):
        contributors = md.get(CONTRIBUTORS_KEY)
        if not contributors:
            return
        clean_contributors = {}
        for role, persons in contributors.items():
            clean_role = cls._clean_charfield(ContributorRole, "name", role)
            clean_persons = set()
            for person in persons:
                clean_person = cls._clean_charfield(ContributorPerson, "name", person)
                if clean_person:
                    clean_persons.add(clean_person)
            clean_contributors[clean_role] = clean_persons
        cls._assign_or_pop(md, CONTRIBUTORS_KEY, clean_contributors)

    @classmethod
    def _clean_story_arcs(cls, md):
        story_arcs = md.get(STORY_ARCS_METADATA_KEY)
        if not story_arcs:
            return
        clean_story_arcs = {}
        for story_arc, number in story_arcs.items():
            clean_story_arc = cls._clean_charfield(StoryArc, "name", story_arc)
            if clean_story_arc:
                clean_story_arcs[clean_story_arc] = number
        cls._assign_or_pop(md, STORY_ARCS_METADATA_KEY, clean_story_arcs)

    @classmethod
    def _clean_identifiers(cls, md):
        identifiers = md.get(IDENTIFIERS_KEY)
        if not identifiers:
            return
        clean_identifiers = {}
        for nid, identifier in identifiers.items():
            clean_id_type = cls._clean_charfield(IdentifierType, "name", nid)
            nss = identifier.get("nss")
            clean_nss = cls._clean_charfield(Identifier, "nss", nss)
            url = identifier.get("url")
            clean_url = cls._clean_charfield(Identifier, "url", url)
            if clean_nss:
                clean_identifier = {"nss": nss}
                if clean_url:
                    clean_identifier["url"] = url
                clean_identifiers[clean_id_type] = clean_identifier
        cls._assign_or_pop(md, IDENTIFIERS_KEY, clean_identifiers)

    @classmethod
    def _clean_md(cls, md):
        """Sanitize the metadata before import."""
        cls._title_to_name(md)
        md = cls._prune_extra_keys(md)
        cls._clean_comic_positive_small_ints(md)
        cls._clean_comic_small_ints(md)
        cls._clean_comic_decimals(md)
        cls._clean_charfields(md)
        cls._clean_contributors(md)
        cls._clean_story_arcs(md)
        cls._clean_identifiers(md)
        return md

    def extract_and_clean(self, path, import_metadata):
        """Extract metadata from comic and clean it for codex."""
        md = {}
        failed_import = {}
        try:
            if import_metadata:
                with Comicbox(path) as cb:
                    md = cb.to_dict()
                    md = md.get("comicbox", {})
                    if "file_type" not in md:
                        md["file_type"] = cb.get_file_type()
                    if "page_count" not in md:
                        md["page_count"] = cb.get_page_count()
            md["path"] = path
            md = self._clean_md(md)
        except (UnsupportedArchiveTypeError, BadRarFile, BadZipFile, OSError) as exc:
            self.log.warning(f"Failed to import {path}: {exc}")
            failed_import = {path: exc}
        except Exception as exc:
            self.log.exception(f"Failed to import: {path}")
            failed_import = {path: exc}
        if failed_import:
            self.metadata[FIS].update(failed_import)
        return md
