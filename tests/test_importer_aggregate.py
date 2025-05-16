"""Test extract metadata importer."""

from decimal import Decimal
from pathlib import Path
from pprint import pformat, pprint
from types import MappingProxyType

from deepdiff import DeepDiff
from django.test import TestCase
from glom import Path as GlomPath
from glom import delete
from loguru import logger

from codex.librarian.importer.const import (
    COMIC_VALUES,
    FIS,
    FK_LINK,
    M2M_LINK,
    QUERY_MODELS,
)
from codex.librarian.importer.importer import ComicImporter
from codex.librarian.importer.tasks import ImportDBDiffTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.models.groups import Imprint, Publisher, Series, Volume
from codex.models.named import (
    AgeRating,
    Character,
    Country,
    Credit,
    CreditPerson,
    CreditRole,
    Genre,
    IdentifierType,
    Language,
    Location,
    OriginalFormat,
    SeriesGroup,
    StoryArc,
    StoryArcNumber,
    Tag,
    Tagger,
    Team,
)

PATH = str(Path(__file__).parent / "files/comicbox-2-example.cbz")
TASK = ImportDBDiffTask(1, files_modified=frozenset({PATH}))
FOLDERS_KEYPATH = GlomPath(M2M_LINK, PATH, "folders")


METADATA = MappingProxyType(
    {
        FIS: {},
        QUERY_MODELS: {
            AgeRating: {"Everyone"},
            # alternate_images ignored
            Character: {"Captain Science", "Boy Empirical"},
            "comic_paths": frozenset({PATH}),
            Country: {"US"},
            Credit: {
                ("Joe Orlando", "Writer"),
                ("Wally Wood", "Penciller"),
            },
            CreditPerson: {"Joe Orlando", "Wally Wood"},
            CreditRole: {"Penciller", "Writer"},
            # credit_primaries ignored
            # Designation: "4242", future
            Genre: {"Science Fiction"},
            Language: {"en"},
            Location: {"The Moon"},
            OriginalFormat: {"Trade Paperback"},
            SeriesGroup: {"science comics"},
            Tag: {"a", "b", "c"},
            Tagger: {"comicbox dev"},
            Publisher: {("Youthful Adventure Stories",): None},
            Imprint: {
                ("Youthful Adventure Stories", "TestImprint"): None,
            },
            Series: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                ): None,
            },
            Volume: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    None,
                ): 7,
            },
            Team: {"Team Scientific Method"},
            IdentifierType: {"comicvine"},
            # "protagonist": {"Captain Science"}, future
            # prices future
            # "stories": ["The Beginning"] future
            StoryArc: {"d", "e", "f"},
            StoryArcNumber: {("d", 1), ("e", 3), ("f", 5)},
            # "universes": {("Young Adult Silly Universe", "4242")}, future
        },
        COMIC_VALUES: {
            PATH: {
                # bookmark ignore
                # cover_date ignore?
                "day": 1,
                # ext ignore
                "file_type": "CBZ",
                "issue": "1.2S",
                "issue_number": Decimal("1.2"),
                "issue_suffix": "S",
                "monochrome": False,
                "month": 11,
                "name": "The Beginning",
                "notes": "Tagged with comicbox dev on 1970-01-01T00:00:00 [Issue ID 145269] urn:comicvine:4000-145269",
                "page_count": 1,
                "path": PATH,
                "reading_direction": "ltr",
                # remainders ignore
                "summary": "Captain Science's many scientific adventures",
                # updated_at ignore
                "year": 1950,
            }
        },
        FK_LINK: {
            PATH: {
                "age_rating": "Everyone",
                "country": "US",
                "imprint": {
                    ("Youthful Adventure Stories", "TestImprint"): None,
                },
                "language": "en",
                "original_format": "Trade Paperback",
                "publisher": {("Youthful Adventure Stories",): None},
                # protagonist
                "series": {
                    (
                        "Youthful Adventure Stories",
                        "TestImprint",
                        "Captain Science",
                    ): None,
                },
                "tagger": "comicbox dev",
                "volume": {
                    (
                        "Youthful Adventure Stories",
                        "TestImprint",
                        "Captain Science",
                        None,
                    ): 7,
                },
            }
        },
        M2M_LINK: {
            PATH: {
                "characters": {"Boy Empirical", "Captain Science"},
                "contributors": {
                    ("Joe Orlando", "Writer"),
                    ("Wally Wood", "Penciller"),
                },
                # "folders": "", varies by filesystem
                "genres": {"Science Fiction"},
                "identifiers": {
                    (
                        "comicvine",
                        "145269",
                        "https://comicvine.gamespot.com/c/4000-145269/",
                    )
                },
                "locations": {"The Moon"},
                # reprints add
                "series_groups": {"science comics"},
                "story_arc_numbers": {("d", 1), ("e", 3), ("f", 5)},
                "tags": {"a", "b", "c"},
                "teams": {"Team Scientific Method"},
                # "universes": { "Silly Universe": { "designation": "4242"}}
            }
        },
    }
)


class TestImporterAggregate(TestCase):
    def test_importer_aggregate(self):
        importer = ComicImporter(TASK, logger, LIBRARIAN_QUEUE)
        importer.extract_metadata()
        importer.aggregate_metadata()
        md = delete(importer.metadata, FOLDERS_KEYPATH)
        md = MappingProxyType(md)
        diff = DeepDiff(METADATA, md)
        if diff:
            Path("old.py").write_text(pformat(METADATA))
            Path("new.py").write_text(pformat(md))
            pprint(diff)
            pprint(md)
        assert not diff


if __name__ == "__main__":
    TestImporterAggregate().test_importer_aggregate()
