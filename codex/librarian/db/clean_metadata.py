"""Clean metadata before importing."""
from decimal import Decimal
from typing import Any, Optional

from django.db.models.fields import CharField, DecimalField, PositiveSmallIntegerField

from codex.models import BrowserGroupModel, Comic, NamedModel


_MD_INVALID_KEYS = frozenset(
    (
        "created_at",
        "id",
        "library",
        "parent_folder",
        "pk",
        "stat",
        "title",
        "updated_at",
    )
)
_MD_VALID_KEYS = (
    frozenset([field.name for field in Comic._meta.get_fields()]) - _MD_INVALID_KEYS
)
_MD_DECIMAL_KEYS = frozenset(("issue", "community_rating", "critical_rating"))
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
        "cover_path",
        "format",
        "language",
        "name",
        "path",
        "scan_info",
    )
)
# _MD_TEXT_KEYS = frozenset(("comments", "notes", "summary"))
_TWO_PLACES = Decimal("0.01")
_PSI_MAX = 2147483647
# _TEXT_MAX_LENGTH = 9**10
GROUPS = frozenset(("publisher", "imprint", "series", "volume"))
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


def _clean_comic_decimals(md: dict[str, Any], md_keys: frozenset[str]) -> None:
    """Clean decimal values."""
    for key in _MD_DECIMAL_KEYS & md_keys:
        field: DecimalField = Comic._meta.get_field(key)  # type:ignore
        try:
            value = md[key]
            value = value.quantize(_TWO_PLACES)
            value = value.max(_DECIMAL_ZERO)
            decimal_max = Decimal(10 ** (field.max_digits - 2) - 1)
            value = value.min(decimal_max)
        except Exception:
            if field.null:
                value = None
            else:
                value = _DECIMAL_ZERO
        md[key] = value


def _clean_comic_positive_small_ints(
    md: dict[str, Any], md_keys: frozenset[str]
) -> None:
    """Clean positive small integers."""
    for key in _MD_PSI_KEYS & md_keys:
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


def _append_description(md) -> None:
    """Append the CoMet description to the CIX summary."""
    if description := md.get("description", ""):
        summary: str = md.get("summary", "")
        if summary:
            summary += "\n"
        summary += description
        md["summary"] = summary


def _title_to_name(md):
    """Convert title to name for comics."""
    try:
        md["name"] = md.pop("title")
    except KeyError:
        pass


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


def _clean_comic_groups(md: dict[str, Any], md_keys: frozenset[str]) -> None:
    """Clean the comic groups."""
    field: CharField = BrowserGroupModel._meta.get_field("name")  # type:ignore
    for group in GROUPS & md_keys:
        md[group] = _clean_charfield(md[group], field)


def _clean_comic_charfields(md: dict[str, Any], md_keys: frozenset[str]) -> None:
    """Clean all the comic charfields."""
    for key in _MD_CHAR_KEYS & md_keys:
        field: CharField = Comic._meta.get_field(key)  # type:ignore
        md[key] = _clean_charfield(md[key], field)


def _clean_comic_credits(md) -> None:
    if credits := md.get("credits"):
        good_credits = list()
        field: CharField = NamedModel._meta.get_field("name")  # type:ignore
        for credit in credits:
            person = _clean_charfield(credit.get("person"), field)
            if person:
                role = _clean_charfield(credit.get("role"), field)
                good_credit = {"role": role, "person": person}
                good_credits.append(good_credit)
        md["credits"] = good_credits


def _clean_comic_web(md):
    """URL field is a special charfield."""
    if "web" not in md:
        return
    try:
        md["web"] = md["web"][:_URL_MAX_LENGTH]
    except Exception:
        del md["web"]


def _clean_comic_m2m_named(md: dict[str, Any], md_keys: frozenset[str]):
    """Clean the named models in the m2m fields."""
    for key in _M2M_NAMED_KEYS & md_keys:
        names = md.get(key)
        if not names:
            continue
        cleaned_names = []
        field: CharField = NamedModel._meta.get_field("name")  # type:ignore
        for name in names:
            cleaned_name = _clean_charfield(name, field)
            if cleaned_name:
                cleaned_names.append(cleaned_name)
        return cleaned_names


def _remove_unused_keys(md: dict[str, Any]) -> frozenset[str]:
    """Remove unused keys."""
    md_keys = frozenset(md.keys())
    unused_keys = md_keys - _MD_VALID_KEYS
    for key in unused_keys:
        del md[key]
    return frozenset(md.keys())


def clean_md(md):
    """Sanitize the metadata before import."""
    _title_to_name(md)
    md_keys = _remove_unused_keys(md)
    _clean_comic_groups(md, md_keys)
    _clean_comic_decimals(md, md_keys)
    _clean_comic_positive_small_ints(md, md_keys)
    _clean_comic_charfields(md, md_keys)
    _clean_comic_web(md)
    _append_description(md)
    _clean_comic_credits(md)
    _clean_comic_m2m_named(md, md_keys)
