"""Clean metadata before importing."""
import re
from decimal import Decimal
from typing import Any, Optional

from comicbox.metadata.comic_base import ComicBaseMetadata
from django.db.models.fields import CharField, DecimalField, PositiveSmallIntegerField

from codex.models import BrowserGroupModel, Comic, NamedModel
from codex.threads import QueuedThread

_MD_INVALID_KEYS = frozenset(
    (
        "id",
        "created_at",
        "library",
        "parent_folder",
        "pk",
        "stat",
        "updated_at",
    )
)
_MD_VALID_KEYS = (
    frozenset([field.name for field in Comic._meta.get_fields()]) - _MD_INVALID_KEYS
)
_MD_DECIMAL_KEYS = frozenset(("community_rating", "critical_rating"))
_MD_PSI_KEYS = frozenset(
    (
        "year",
        "month",
        "day",
        "page_count",
    )  # computed by presave: ("decade", "max_page", "size")
)
_MD_CHAR_KEYS = frozenset(
    (
        "age_rating",
        "country",
        "cover_pk",
        "file_format",
        "format",
        "issue_suffix",
        "language",
        "name",
        "path",
        "scan_info",
    )
)
_TWO_PLACES = Decimal("0.01")
_PSI_MAX = 2147483647
_GROUPS = frozenset(("publisher", "imprint", "series", "volume"))
_URL_MAX_LENGTH = 200
_M2M_NAMED_KEYS = frozenset(
    (
        "characters",
        "genres",
        "locations",
        "series_groups",
        "story_arcs",
        "tags",
        "teams",
    )
)
_DECIMAL_ZERO = Decimal("0.00")
_PARSE_ISSUE_REGEX = r"(\d*\.?\d*)(.*)"
_PARSE_ISSUE_MATCHER = re.compile(_PARSE_ISSUE_REGEX)


class CleanMetadataMixin(QueuedThread):
    """Clean metadata before importing."""

    @staticmethod
    def _clean_decimal(value, field_name: str):
        field: DecimalField = Comic._meta.get_field(field_name)  # type: ignore
        try:
            # Comicbox now gives issues as strings, convert them to decimal here.
            value = ComicBaseMetadata.parse_decimal(value)
            value = value.quantize(_TWO_PLACES)
            value = value.max(_DECIMAL_ZERO)
            decimal_max = Decimal(10 ** (field.max_digits - 2) - 1)
            value = value.min(decimal_max)
        except Exception:
            if field.null:
                value = None
            else:
                value = _DECIMAL_ZERO
        return value

    def _parse_comic_issue(self, md: dict[str, Any]):
        """Parse the issue field."""
        issue_str = md.get("issue", "").strip()
        try:
            match = _PARSE_ISSUE_MATCHER.match(issue_str)
            issue, issue_suffix = match.groups()  # type: ignore
            md["issue"] = self._clean_decimal(issue, "issue")
            md["issue_suffix"] = self._clean_charfield(
                issue_suffix, Comic._meta.get_field("issue_suffix")  # type: ignore
            )
        except Exception as exc:
            self.log.warning(f"parsing issue failed: {issue_str} {exc}")
            md["issue"] = None
            md["issue_suffix"] = issue_str

    @classmethod
    def _clean_comic_decimals(cls, md: dict[str, Any], md_keys: frozenset[str]) -> None:
        """Clean decimal values."""
        for key in _MD_DECIMAL_KEYS.intersection(md_keys):
            value = md.get(key)
            md[key] = cls._clean_decimal(value, key)

    @staticmethod
    def _clean_comic_positive_small_ints(
        md: dict[str, Any], md_keys: frozenset[str]
    ) -> None:
        """Clean positive small integers."""
        for key in _MD_PSI_KEYS.intersection(md_keys):
            field: PositiveSmallIntegerField = Comic._meta.get_field(key)  # type:ignore
            try:
                value = md[key]
                value = int(value)
                value = max(0, value)
                value = min(value, _PSI_MAX)
            except Exception:
                if field.null:
                    value = None
                else:
                    value = 0
            md[key] = value

    @staticmethod
    def _append_description(md) -> None:
        """Append the CoMet description to the CIX summary."""
        if description := md.get("description", ""):
            summary: str = md.get("summary", "")
            if summary:
                summary += "\n"
            summary += description
            md["summary"] = summary

    @staticmethod
    def _title_to_name(md):
        """Convert title to name for comics."""
        try:
            md["name"] = md.pop("title")
        except KeyError:
            pass

    @staticmethod
    def _clean_charfield(value: Optional[str], field: CharField) -> Optional[str]:
        try:
            if value is None:
                raise ValueError()
            value = value[: field.max_length].strip()
        except Exception:
            if field.null:
                value = None
            else:
                value = ""
        return value

    @classmethod
    def _clean_comic_groups(cls, md: dict[str, Any], md_keys: frozenset[str]) -> None:
        """Clean the comic groups."""
        field: CharField = BrowserGroupModel._meta.get_field("name")  # type:ignore
        for group in _GROUPS.intersection(md_keys):
            md[group] = cls._clean_charfield(md[group], field)

    @classmethod
    def _clean_comic_charfields(
        cls, md: dict[str, Any], md_keys: frozenset[str]
    ) -> None:
        """Clean all the comic charfields."""
        for key in _MD_CHAR_KEYS.intersection(md_keys):
            field: CharField = Comic._meta.get_field(key)  # type:ignore
            md[key] = cls._clean_charfield(md[key], field)

    @classmethod
    def _clean_comic_credits(cls, md) -> None:
        if credits := md.get("credits"):
            good_credits = []
            field: CharField = NamedModel._meta.get_field("name")  # type:ignore
            for credit in credits:
                person = cls._clean_charfield(credit.get("person"), field)
                if person:
                    role = cls._clean_charfield(credit.get("role"), field)
                    good_credit = {"role": role, "person": person}
                    good_credits.append(good_credit)
            md["credits"] = good_credits

    @staticmethod
    def _clean_comic_web(md):
        """URL field is a special charfield."""
        if "web" not in md:
            return
        try:
            md["web"] = md["web"][:_URL_MAX_LENGTH]
        except Exception:
            del md["web"]

    @classmethod
    def _clean_comic_m2m_named(cls, md: dict[str, Any], md_keys: frozenset[str]):
        """Clean the named models in the m2m fields."""
        for key in _M2M_NAMED_KEYS.intersection(md_keys):
            names = md.get(key)
            if not names:
                continue
            cleaned_names = []
            field: CharField = NamedModel._meta.get_field("name")  # type:ignore
            for name in names:
                cleaned_name = cls._clean_charfield(name, field)
                if cleaned_name:
                    cleaned_names.append(cleaned_name)
            md[key] = cleaned_names

    @staticmethod
    def _allowed_keys(dirty_md: dict[str, Any]) -> dict[str, Any]:
        """Remove unused keys."""
        allowed_md = {}
        for key in _MD_VALID_KEYS:
            val = dirty_md.get(key)
            if val is not None:
                allowed_md[key] = val
        return allowed_md

    def clean_md(self, md):
        """Sanitize the metadata before import."""
        self._parse_comic_issue(md)
        self._title_to_name(md)
        md = self._allowed_keys(md)
        md_keys = frozenset(md.keys())
        self._clean_comic_groups(md, md_keys)
        self._clean_comic_decimals(md, md_keys)
        self._clean_comic_positive_small_ints(md, md_keys)
        self._clean_comic_charfields(md, md_keys)
        self._clean_comic_web(md)
        self._append_description(md)
        self._clean_comic_credits(md)
        self._clean_comic_m2m_named(md, md_keys)
        return md
