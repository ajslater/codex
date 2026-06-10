"""
Tests for the 0043 ``relink_age_rating_metron`` data migration.

``AgeRating.metron`` is normally derived once, in ``presave`` at row
creation, so mappings comicbox gains later (e.g. ``Rating Pending`` ->
``Unknown``) never reach existing rows. The migration recomputes every
FK with the live comicbox mapping and heals the denormalizations that
derive from it: ``Comic.age_rating_metron_index`` and the FTS watermark
(via an ``updated_at`` bump).
"""

import importlib
import shutil
from pathlib import Path
from typing import override

from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.apps import apps
from django.test import TestCase

from codex.models import (
    AgeRating,
    AgeRatingMetron,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.age_rating import UNRANKED_METRON_INDEX

_MIGRATION = importlib.import_module("codex.migrations.0043_comicbox_tagging_defaults")
relink_age_rating_metron = _MIGRATION.relink_age_rating_metron

TMP_DIR = Path("/tmp/codex.tests.age-rating-relink")  # noqa: S108


class AgeRatingRelinkMigrationTestCase(TestCase):
    """Exercise the relink against stale, wrong, and already-correct rows."""

    @override
    def setUp(self) -> None:
        """Seed comics whose AgeRating links predate the current mapping."""
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )

        def _comic_with(name: str, age_rating: AgeRating, index: int | None) -> Comic:
            path = TMP_DIR / f"{name}.cbz"
            path.touch()
            return Comic.objects.create(
                library=library,
                path=path,
                issue_number=1,
                name=name,
                publisher=publisher,
                imprint=imprint,
                series=series,
                volume=volume,
                size=1,
                age_rating=age_rating,
                age_rating_metron_index=index,
            )

        # Imported before comicbox learned Rating Pending -> Unknown:
        # FK NULL, denormalized index NULL.
        self.pending = AgeRating.objects.create(name="Rating Pending", metron=None)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.pending_comic = _comic_with("pending", self.pending, None)  # pyright: ignore[reportUninitializedInstanceVariable]

        # Linked to the wrong metron row (mapping changed since import).
        wrong = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.ADULT.value)
        self.pg = AgeRating.objects.create(name="PG", metron=wrong)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.pg_comic = _comic_with("pg", self.pg, wrong.index)  # pyright: ignore[reportUninitializedInstanceVariable]

        # Already correct: must not be touched (no updated_at bump).
        teen_metron = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.TEEN.value)
        self.teen = AgeRating.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name=MetronAgeRatingEnum.TEEN.value, metron=teen_metron
        )
        self.teen_comic = _comic_with("teen", self.teen, teen_metron.index)  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        """Remove the comic stub files."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        super().tearDown()

    def test_relink_heals_stale_links_and_denormalizations(self) -> None:
        """NULL and wrong FKs are recomputed; comic index + updated_at follow."""
        teen_updated_at = self.teen_comic.updated_at

        relink_age_rating_metron(apps, None)

        self.pending.refresh_from_db()
        self.pending_comic.refresh_from_db()
        assert self.pending.metron is not None
        assert self.pending.metron.name == MetronAgeRatingEnum.UNKNOWN.value
        assert self.pending_comic.age_rating_metron_index == UNRANKED_METRON_INDEX
        assert self.pending_comic.updated_at > teen_updated_at

        self.pg.refresh_from_db()
        self.pg_comic.refresh_from_db()
        assert self.pg.metron is not None
        assert self.pg.metron.name == MetronAgeRatingEnum.TEEN.value
        assert self.pg_comic.age_rating_metron_index == self.pg.metron.index

        # The correct row is untouched — its comic keeps its timestamp.
        self.teen_comic.refresh_from_db()
        assert self.teen_comic.updated_at == teen_updated_at

    def test_relink_is_idempotent(self) -> None:
        """A second run finds nothing to update and bumps no timestamps."""
        relink_age_rating_metron(apps, None)
        self.pending_comic.refresh_from_db()
        first_updated_at = self.pending_comic.updated_at

        relink_age_rating_metron(apps, None)

        self.pending_comic.refresh_from_db()
        assert self.pending_comic.updated_at == first_updated_at
