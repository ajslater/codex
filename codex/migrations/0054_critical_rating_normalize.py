"""
Normalize ``Comic.critical_rating`` to the ComicInfo 0.0-5.0 scale (1 dp).

Historical state: ``critical_rating`` was a ``DecimalField(max_digits=5,
decimal_places=2)`` accepting anything 0.00-999.99. Comicbox forwarded
ComicInfo ``CommunityRating`` (spec 0-5) and ComicBookInfo ``rating``
(unspecified integer, often 0-10 or 0-100) into the same field with no
scale conversion. Mock-comic seeds further polluted dev DBs with
``random.random() * 100 * 1.1`` values.

Going forward, comicbox normalizes both source formats to the
ComicInfo scale on read. This migration applies the same algorithm to
existing rows so the on-disk canon matches the new ingest contract,
then shrinks the column to ``max_digits=2, decimal_places=1``.

Heuristic:

    * ``value <= 5``  -> already canonical (assume legit ComicInfo)
    * ``5 < value <= 10``  -> divide by 2
    * ``10 < value <= 100``  -> divide by 20
    * ``100 < value <= 1000``  -> divide by 200
    * ...generalized as ``2 * 10^(ceil(log10(value)) - 1)``.

The "<= 5 means legit" rule will misclassify any historical
ComicBookInfo ``rating=3`` (which should canonicalize to ``1.5``) as
already-canonical ``3.0``. There is no provenance left in the DB to
tell them apart; the user accepted this trade-off.
"""

from decimal import ROUND_HALF_UP, Decimal
from math import ceil, log10

import django.core.validators
from django.db import migrations
from loguru import logger

import codex.models.fields

_ONE_DP = Decimal("0.1")
_MAX = Decimal("5.0")
_CHUNK_SIZE = 2000


def _normalize(value: Decimal | None) -> Decimal | None:
    """Apply the comicbox-style CBI bucketing to a single rating."""
    if value is None:
        return None
    if value <= _MAX:
        return value.quantize(_ONE_DP, rounding=ROUND_HALF_UP)
    if value <= Decimal(10):
        divisor = Decimal(2)
    else:
        implied_max = Decimal(10) ** ceil(log10(float(value)))
        divisor = implied_max / _MAX
    result = (value / divisor).quantize(_ONE_DP, rounding=ROUND_HALF_UP)
    return min(result, _MAX)


def normalize_critical_ratings(apps, _schema_editor) -> None:
    """Rescale and quantize every non-null ``Comic.critical_rating``."""
    comic_model = apps.get_model("codex", "comic")
    qs = comic_model.objects.exclude(critical_rating__isnull=True).only(
        "pk", "path", "critical_rating"
    )
    updates: list = []
    for comic in qs.iterator(chunk_size=_CHUNK_SIZE):
        before = comic.critical_rating
        after = _normalize(before)
        if after == before:
            continue
        logger.info(f"critical_rating: {before} -> {after} ({comic.path})")
        comic.critical_rating = after
        updates.append(comic)
        if len(updates) >= _CHUNK_SIZE:
            comic_model.objects.bulk_update(updates, ("critical_rating",))
            updates = []
    if updates:
        comic_model.objects.bulk_update(updates, ("critical_rating",))


def _noop_reverse(_apps, _schema_editor) -> None:
    """No reverse: the rescale is intentionally lossy."""


class Migration(migrations.Migration):
    """Rescale critical_rating to 0-5 and shrink the column."""

    dependencies = [
        ("codex", "0053_drop_tagging_session_state"),
    ]

    operations = [
        migrations.RunPython(normalize_critical_ratings, _noop_reverse),
        migrations.AlterField(
            model_name="comic",
            name="critical_rating",
            field=codex.models.fields.CoercingDecimalField(  # pyright: ignore[reportCallIssue]  # ty: ignore[no-matching-overload]
                coerce_max=Decimal("5.0"),
                db_index=True,
                decimal_places=1,
                default=None,
                max_digits=2,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.0")),
                    django.core.validators.MaxValueValidator(Decimal("5.0")),
                ],
            ),
        ),
    ]
