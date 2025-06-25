"""Test extract metadata importer."""

import os
import shutil
from abc import ABC
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from pprint import pformat, pprint
from threading import Event
from types import MappingProxyType

from deepdiff import DeepDiff
from django.core.cache import cache
from django.test import TestCase
from django.test.testcases import SerializeMixin
from glom import Path as GlomPath
from loguru import logger
from typing_extensions import override

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer import ComicImporter
from codex.librarian.scribe.importer.const import (
    CREATE_COMICS,
    CREATE_FKS,
    DELETE_M2MS,
    FIS,
    LINK_FKS,
    LINK_M2MS,
    QUERY_MODELS,
    TOTAL,
    UPDATE_COMICS,
    UPDATE_FKS,
)
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import (
    AgeRating,
    Character,
    Comic,
    Country,
    Credit,
    CreditPerson,
    CreditRole,
    Folder,
    Genre,
    Identifier,
    IdentifierSource,
    Imprint,
    Language,
    Location,
    OriginalFormat,
    Publisher,
    ScanInfo,
    Series,
    SeriesGroup,
    Story,
    StoryArc,
    StoryArcNumber,
    Tag,
    Tagger,
    Team,
    Universe,
    Volume,
)
from codex.models.library import Library
from codex.startup import codex_init
from codex.util import flatten

TMP_DIR = Path("/tmp") / Path(__file__).stem  # noqa: S108
LIBRARY_PATH = TMP_DIR
FILES_DIR = Path(__file__).parent / "files"
COMIC_PATH = FILES_DIR / "comicbox-2-example.cbz"
UPDATE_PATH = FILES_DIR / "comicbox-2-update.cbz"
PATH = str(LIBRARY_PATH / "test.cbz")
PATH_PARENTS = {(str(Path(PATH).parent),)}
FOLDERS_LINK_KEYPATH = GlomPath(LINK_M2MS, PATH, "folders")
FOLDERS_QUERY_MODELS_KEYPATH = GlomPath(QUERY_MODELS, Folder)
FLAT_PATH_PARENTS = flatten(frozenset(PATH_PARENTS))
CHARACTER_NAMES = (
    "Boy Empirical",
    "Captain Science",
)
UPDATED_CHARACTER_NAMES = ("Captain Science",)


AGGREGATED_METADATA = MappingProxyType(
    {
        FIS: {},
        QUERY_MODELS: {
            AgeRating: {("Everyone",)},
            # alternate_images ignored
            Character: {
                ("Captain Science", None),
                ("Boy Empirical", ("metron", "character", "345")),
            },
            Folder: deepcopy(PATH_PARENTS),
            Country: {("US",)},
            Credit: {
                ("Joe Orlando", "Writer"),
                ("Wally Wood", "Penciller"),
            },
            CreditPerson: {("Joe Orlando", None), ("Wally Wood", None)},
            CreditRole: {("Penciller", None), ("Writer", None)},
            # credit_primaries ignored
            Genre: {("Science Fiction", None)},
            Language: {("en",)},
            Location: {("The Moon", None)},
            OriginalFormat: {("Trade Paperback",)},
            Tag: {("a", None), ("b", None), ("c", None)},
            Tagger: {("comicbox dev",)},
            Publisher: {("Youthful Adventure Stories", None)},
            Imprint: {
                ("Youthful Adventure Stories", "TestImprint", None),
            },
            ScanInfo: {("Photocopied",)},
            Series: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    None,
                    None,
                )
            },
            SeriesGroup: {("science comics",)},
            Volume: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                    7,
                ),
            },
            Team: {("Team Scientific Method", None)},
            IdentifierSource: {("comicvine",), ("metron",)},
            Identifier: {
                (
                    "comicvine",
                    "comic",
                    "145269",
                    "https://comicvine.gamespot.com/c/4000-145269/",
                ),
                ("metron", "character", "345", "https://metron.cloud/character/345"),
                ("metron", "storyarc", "123", "https://metron.cloud/arc/123"),
            },
            # prices future
            Story: {("The Beginning", None)},
            StoryArc: {
                ("c", None),
                ("d", ("metron", "storyarc", "123")),
                ("e", None),
                ("f", None),
            },
            StoryArcNumber: {
                ("c", None),
                ("d", 1),
                ("e", 3),
                ("f", 5),
            },
            Universe: {("Young Adult Silly Universe", None, "4242")},
        },
        CREATE_COMICS: {
            PATH: {
                # bookmark ignore
                # cover_date ignore?
                "collection_title": "The Big Omnibus",
                "critical_rating": Decimal("10.00"),
                "day": 1,
                # ext ignore
                "file_type": "CBZ",
                "issue_number": Decimal("1.2"),
                "issue_suffix": "S",
                "metadata_mtime": datetime(2025, 5, 24, 0, 33, 26, tzinfo=timezone.utc),
                "monochrome": False,
                "month": 11,
                "name": "The Beginning",
                "notes": (
                    "Tagged with comicbox dev on 1970-01-01T00:00:00 [Issue ID 145269] "
                    "urn:comicvine:4000-145269"
                ),
                "page_count": 1,
                "path": PATH,
                "reading_direction": "ltr",
                "review": "It wasn't all bad.",
                # remainders ignore
                "summary": "Captain Science's many scientific adventures",
                # updated_at ignore
                "year": 1950,
            }
        },
        LINK_FKS: {
            PATH: {
                "age_rating": ("Everyone",),
                "country": ("US",),
                "imprint": ("Youthful Adventure Stories", "TestImprint"),
                "language": ("en",),
                "original_format": ("Trade Paperback",),
                "publisher": ("Youthful Adventure Stories",),
                "protagonist": ("Captain Science",),
                "scan_info": ("Photocopied",),
                "series": (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                ),
                "tagger": ("comicbox dev",),
                "volume": (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                ),
            }
        },
        LINK_M2MS: {
            PATH: {
                "characters": {
                    ("Boy Empirical",),
                    ("Captain Science",),
                },
                "credits": {
                    ("Wally Wood", "Penciller"),
                    ("Joe Orlando", "Writer"),
                },
                "genres": {("Science Fiction",)},
                "folders": deepcopy(PATH_PARENTS),
                "identifiers": {
                    (
                        "comicvine",
                        "comic",
                        "145269",
                    )
                },
                "locations": {("The Moon",)},
                # reprints add
                "series_groups": {("science comics",)},
                "stories": {("The Beginning",)},
                "story_arc_numbers": {
                    ("c", None),
                    ("d", 1),
                    ("e", 3),
                    ("f", 5),
                },
                "tags": {("a",), ("b",), ("c",)},
                "teams": {("Team Scientific Method",)},
                "universes": {("Young Adult Silly Universe",)},
            }
        },
    }
)
AGGREGATED_METADATA_UPDATE_ALL = MappingProxyType(
    {
        CREATE_COMICS: {
            PATH: {
                "collection_title": "The Big Omnibus Part 2",
                "critical_rating": Decimal("5.00"),
                "day": 20,
                "file_type": "CBZ",
                "issue_number": Decimal("2.2"),
                "issue_suffix": "XXX",
                "metadata_mtime": datetime(
                    2025, 6, 15, 18, 13, 44, tzinfo=timezone.utc
                ),
                "monochrome": True,
                "month": 12,
                "name": "The Beginning; The End",
                "notes": (
                    "Tagged with comicbox dev on 1970-01-01T00:00:00 [Issue ID 145269] "
                    "urn:comicvine:4000-145265"
                ),
                "page_count": 0,
                "path": PATH,
                "reading_direction": "rtl",
                "review": "Actually unreadable.",
                "summary": "Captain Science's many adult adventures",
                "year": 1951,
            }
        },
        FIS: {},
        LINK_FKS: {
            PATH: {
                "age_rating": ("Adult",),
                "country": ("GB",),
                "imprint": ("Youthful Adventure Stories", "TestImprint"),
                "language": ("fr",),
                "original_format": ("Hardcover",),
                "protagonist": ("Team Cornish Game Hen",),
                "publisher": ("Youthful Adventure Stories",),
                "scan_info": ("Digital",),
                "series": (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                ),
                "tagger": ("comicbox dev",),
                "volume": (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                ),
            }
        },
        LINK_M2MS: {
            PATH: {
                "characters": {("Captain Science",)},
                "credits": {("Joe Orlando", "Writer"), ("Wally Wood", "Penciller")},
                "folders": deepcopy(PATH_PARENTS),
                "genres": {("Mystery",), ("Science Fiction",)},
                "identifiers": {
                    ("comicvine", "comic", "145265"),
                    ("metron", "comic", "999"),
                },
                "locations": {("Mars",)},
                "series_groups": {("adult comics",)},
                "stories": {("The Beginning",), ("The End",)},
                "story_arc_numbers": {("c", None), ("d", 1), ("e", 3), ("g", 5)},
                "universes": {("Young Adult Silly Universe",)},
                "tags": {("a",), ("c",)},
            }
        },
        QUERY_MODELS: {
            IdentifierSource: {("comicvine",), ("metron",)},
            Identifier: {
                (
                    "comicvine",
                    "comic",
                    "145265",
                    "https://comicvine.gamespot.com/c/4000-145265/",
                ),
                (
                    "comicvine",
                    "location",
                    "111",
                    "https://comicvine.gamespot.com/c/4020-111/",
                ),
                (
                    "comicvine",
                    "series",
                    "333",
                    "https://comicvine.gamespot.com/c/4050-333/",
                ),
                (
                    "comicvine",
                    "storyarc",
                    "456",
                    "https://comicvine.gamespot.com/c/4045-456/",
                ),
                (
                    "comicvine",
                    "storyarc",
                    "890",
                    "https://comicvine.gamespot.com/c/4045-890/",
                ),
                ("metron", "character", "123", "https://metron.cloud/character/123"),
                ("metron", "comic", "999", "https://metron.cloud/issue/999"),
                ("metron", "creditperson", "123", "https://metron.cloud/creator/123"),
                ("metron", "genre", "012", "https://metron.cloud/genre/012"),
                ("metron", "imprint", "123", "https://metron.cloud/imprint/123"),
                ("metron", "publisher", "111", "https://metron.cloud/publisher/111"),
                ("metron", "story", "555", "https://metron.cloud/story/555"),
            },
            Publisher: {
                (
                    "Youthful Adventure Stories",
                    ("metron", "publisher", "111"),
                )
            },
            Imprint: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    ("metron", "imprint", "123"),
                )
            },
            Series: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    ("comicvine", "series", "333"),
                    None,
                )
            },
            Language: {("fr",)},
            Volume: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                    1,
                )
            },
            Folder: deepcopy(PATH_PARENTS),
            AgeRating: {("Adult",)},
            Character: {("Captain Science", ("metron", "character", "123"))},
            CreditPerson: {
                ("Joe Orlando", ("metron", "creditperson", "123")),
                ("Wally Wood", None),
            },
            CreditRole: {("Penciller", None), ("Writer", None)},
            Credit: {("Joe Orlando", "Writer"), ("Wally Wood", "Penciller")},
            Country: {("GB",)},
            Genre: {("Mystery", None), ("Science Fiction", ("metron", "genre", "012"))},
            Location: {("Mars", ("comicvine", "location", "111"))},
            OriginalFormat: {("Hardcover",)},
            ScanInfo: {("Digital",)},
            SeriesGroup: {("adult comics",)},
            Story: {("The Beginning", ("metron", "story", "555")), ("The End", None)},
            StoryArc: {
                ("c", None),
                ("d", ("comicvine", "storyarc", "890")),
                ("e", ("comicvine", "storyarc", "456")),
                ("g", None),
            },
            StoryArcNumber: {("c", None), ("d", 1), ("e", 3), ("g", 5)},
            Tag: {("a", None), ("c", None)},
            Tagger: {("comicbox dev",)},
            Universe: {("Young Adult Silly Universe", None, "6969")},
        },
    }
)
QUERIED_METADATA = MappingProxyType(
    {
        CREATE_COMICS: {
            PATH: {
                "collection_title": "The Big Omnibus",
                "critical_rating": Decimal("10.00"),
                "day": 1,
                "file_type": "CBZ",
                "issue_number": Decimal("1.2"),
                "issue_suffix": "S",
                "metadata_mtime": datetime(2025, 5, 24, 0, 33, 26, tzinfo=timezone.utc),
                "monochrome": False,
                "month": 11,
                "name": "The Beginning",
                "notes": (
                    "Tagged with comicbox dev on 1970-01-01T00:00:00 [Issue ID 145269] "
                    "urn:comicvine:4000-145269"
                ),
                "page_count": 1,
                "path": PATH,
                "reading_direction": "ltr",
                "review": "It wasn't all bad.",
                "summary": "Captain Science's many scientific adventures",
                "year": 1950,
            }
        },
        UPDATE_COMICS: {},
        FIS: {},
        CREATE_FKS: {
            AgeRating: {("Everyone",)},
            IdentifierSource: {("metron",), ("comicvine",)},
            Identifier: {
                (
                    "comicvine",
                    "comic",
                    "145269",
                    "https://comicvine.gamespot.com/c/4000-145269/",
                ),
                ("metron", "character", "345", "https://metron.cloud/character/345"),
                ("metron", "storyarc", "123", "https://metron.cloud/arc/123"),
            },
            Location: {("The Moon", None)},
            Character: {
                (
                    "Boy Empirical",
                    (
                        "metron",
                        "character",
                        "345",
                    ),
                ),
                ("Captain Science", None),
            },
            Country: {("US",)},
            CreditPerson: {("Joe Orlando", None), ("Wally Wood", None)},
            CreditRole: {("Penciller", None), ("Writer", None)},
            Credit: {
                ("Joe Orlando", "Writer"),
                ("Wally Wood", "Penciller"),
            },
            Genre: {("Science Fiction", None)},
            Language: {("en",)},
            OriginalFormat: {("Trade Paperback",)},
            ScanInfo: {("Photocopied",)},
            SeriesGroup: {("science comics",)},
            Story: {("The Beginning", None)},
            StoryArc: {
                ("c", None),
                ("d", ("metron", "storyarc", "123")),
                ("e", None),
                ("f", None),
            },
            StoryArcNumber: {
                ("c", None),
                ("d", 1),
                ("e", 3),
                ("f", 5),
            },
            Tag: {("a", None), ("b", None), ("c", None)},
            Tagger: {("comicbox dev",)},
            Team: {("Team Scientific Method", None)},
            Universe: {("Young Adult Silly Universe", None, "4242")},
            Folder: deepcopy(PATH_PARENTS),
            Publisher: {("Youthful Adventure Stories", None)},
            Imprint: {("Youthful Adventure Stories", "TestImprint", None)},
            Series: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    None,
                    None,
                )
            },
            Volume: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                    7,
                )
            },
            TOTAL: 41,
        },
        UPDATE_FKS: {
            TOTAL: 0,
        },
        LINK_FKS: {
            PATH: {
                "age_rating": ("Everyone",),
                "country": ("US",),
                "imprint": ("Youthful Adventure Stories", "TestImprint"),
                "language": ("en",),
                "original_format": ("Trade Paperback",),
                "protagonist": ("Captain Science",),
                "publisher": ("Youthful Adventure Stories",),
                "scan_info": ("Photocopied",),
                "series": (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                ),
                "tagger": ("comicbox dev",),
                "volume": (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                ),
            }
        },
        LINK_M2MS: {
            PATH: {
                "characters": {("Boy Empirical",), ("Captain Science",)},
                "credits": {("Joe Orlando", "Writer"), ("Wally Wood", "Penciller")},
                "folders": deepcopy(PATH_PARENTS),
                "genres": {("Science Fiction",)},
                "identifiers": {("comicvine", "comic", "145269")},
                "locations": {("The Moon",)},
                "series_groups": {("science comics",)},
                "stories": {("The Beginning",)},
                "story_arc_numbers": {("c", None), ("d", 1), ("e", 3), ("f", 5)},
                "tags": {("a",), ("b",), ("c",)},
                "teams": {("Team Scientific Method",)},
                "universes": {("Young Adult Silly Universe",)},
            }
        },
        DELETE_M2MS: {},
    }
)

CREATED_FK_METADATA = MappingProxyType(
    {
        CREATE_COMICS: {
            PATH: {
                "collection_title": "The Big Omnibus",
                "critical_rating": Decimal("10.00"),
                "day": 1,
                "file_type": "CBZ",
                "issue_number": Decimal("1.2"),
                "issue_suffix": "S",
                "metadata_mtime": datetime(2025, 5, 24, 0, 33, 26, tzinfo=timezone.utc),
                "monochrome": False,
                "month": 11,
                "name": "The Beginning",
                "notes": (
                    "Tagged with comicbox dev on 1970-01-01T00:00:00 [Issue ID 145269] "
                    "urn:comicvine:4000-145269"
                ),
                "page_count": 1,
                "path": PATH,
                "reading_direction": "ltr",
                "review": "It wasn't all bad.",
                "summary": "Captain Science's many scientific adventures",
                "year": 1950,
            }
        },
        UPDATE_COMICS: {},
        FIS: {},
        LINK_FKS: {
            PATH: {
                "age_rating": ("Everyone",),
                "country": ("US",),
                "imprint": ("Youthful Adventure Stories", "TestImprint"),
                "language": ("en",),
                "original_format": ("Trade Paperback",),
                "protagonist": ("Captain Science",),
                "publisher": ("Youthful Adventure Stories",),
                "scan_info": ("Photocopied",),
                "series": (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                ),
                "tagger": ("comicbox dev",),
                "volume": (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                ),
            }
        },
        LINK_M2MS: {
            PATH: {
                "characters": {("Boy Empirical",), ("Captain Science",)},
                "credits": {("Joe Orlando", "Writer"), ("Wally Wood", "Penciller")},
                "folders": deepcopy(PATH_PARENTS),
                "genres": {("Science Fiction",)},
                "identifiers": {("comicvine", "comic", "145269")},
                "locations": {("The Moon",)},
                "series_groups": {("science comics",)},
                "stories": {("The Beginning",)},
                "story_arc_numbers": {("c", None), ("d", 1), ("e", 3), ("f", 5)},
                "tags": {("a",), ("b",), ("c",)},
                "teams": {("Team Scientific Method",)},
                "universes": {("Young Adult Silly Universe",)},
            }
        },
        DELETE_M2MS: {},
    }
)
QUERIED_METADATA_NONE = MappingProxyType(
    {
        CREATE_COMICS: {},
        UPDATE_COMICS: {},
        FIS: {},
        CREATE_FKS: {TOTAL: 0},
        UPDATE_FKS: {TOTAL: 0},
        LINK_FKS: {},
        LINK_M2MS: {},
        DELETE_M2MS: {},
    }
)
QUERIED_METADATA_UPDATE_ALL = MappingProxyType(
    {
        CREATE_COMICS: {},
        CREATE_FKS: {
            Identifier: {
                (
                    "comicvine",
                    "comic",
                    "145265",
                    "https://comicvine.gamespot.com/c/4000-145265/",
                ),
                (
                    "comicvine",
                    "location",
                    "111",
                    "https://comicvine.gamespot.com/c/4020-111/",
                ),
                (
                    "comicvine",
                    "series",
                    "333",
                    "https://comicvine.gamespot.com/c/4050-333/",
                ),
                (
                    "comicvine",
                    "storyarc",
                    "456",
                    "https://comicvine.gamespot.com/c/4045-456/",
                ),
                (
                    "comicvine",
                    "storyarc",
                    "890",
                    "https://comicvine.gamespot.com/c/4045-890/",
                ),
                ("metron", "character", "123", "https://metron.cloud/character/123"),
                ("metron", "comic", "999", "https://metron.cloud/issue/999"),
                ("metron", "creditperson", "123", "https://metron.cloud/creator/123"),
                ("metron", "genre", "012", "https://metron.cloud/genre/012"),
                ("metron", "imprint", "123", "https://metron.cloud/imprint/123"),
                ("metron", "publisher", "111", "https://metron.cloud/publisher/111"),
                ("metron", "story", "555", "https://metron.cloud/story/555"),
            },
            Language: {("fr",)},
            AgeRating: {("Adult",)},
            Country: {("GB",)},
            Genre: {("Mystery", None)},
            Location: {("Mars", ("comicvine", "location", "111"))},
            OriginalFormat: {("Hardcover",)},
            ScanInfo: {("Digital",)},
            SeriesGroup: {("adult comics",)},
            Story: {("The End", None)},
            StoryArc: {("g", None)},
            StoryArcNumber: {("g", 5)},
            "total": 23,
        },
        DELETE_M2MS: {
            "characters": {(1, 1)},
            "identifiers": {(1, 1)},
            "locations": {(1, 1)},
            "series_groups": {(1, 1)},
            "story_arc_numbers": {(1, 4)},
            "tags": {(1, 2)},
        },
        FIS: {},
        LINK_FKS: {
            PATH: {
                "age_rating": ("Adult",),
                "country": ("GB",),
                "language": ("fr",),
                "original_format": ("Hardcover",),
                "protagonist": ("Team Cornish Game Hen",),
                "scan_info": ("Digital",),
            }
        },
        LINK_M2MS: {
            PATH: {
                "genres": {("Mystery",)},
                "identifiers": {
                    ("comicvine", "comic", "145265"),
                    ("metron", "comic", "999"),
                },
                "locations": {("Mars",)},
                "series_groups": {("adult comics",)},
                "stories": {("The End",)},
                "story_arc_numbers": {("g", 5)},
            }
        },
        UPDATE_COMICS: {
            1: {
                "collection_title": "The Big Omnibus Part 2",
                "critical_rating": Decimal("5.00"),
                "day": 20,
                "issue_number": Decimal("2.2"),
                "issue_suffix": "XXX",
                "metadata_mtime": datetime(
                    2025, 6, 15, 18, 13, 44, tzinfo=timezone.utc
                ),
                "monochrome": True,
                "month": 12,
                "name": "The Beginning; The End",
                "notes": (
                    "Tagged with comicbox dev on 1970-01-01T00:00:00 [Issue ID 145269] "
                    "urn:comicvine:4000-145265"
                ),
                "page_count": 0,
                "reading_direction": "rtl",
                "review": "Actually unreadable.",
                "summary": "Captain Science's many adult adventures",
                "year": 1951,
            }
        },
        UPDATE_FKS: {
            Publisher: {("Youthful Adventure Stories", ("metron", "publisher", "111"))},
            Imprint: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    ("metron", "imprint", "123"),
                )
            },
            Series: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    ("comicvine", "series", "333"),
                    None,
                )
            },
            Character: {("Captain Science", ("metron", "character", "123"))},
            CreditPerson: {("Joe Orlando", ("metron", "creditperson", "123"))},
            Genre: {("Science Fiction", ("metron", "genre", "012"))},
            Story: {("The Beginning", ("metron", "story", "555"))},
            StoryArc: {
                ("d", ("comicvine", "storyarc", "890")),
                ("e", ("comicvine", "storyarc", "456")),
            },
            Universe: {("Young Adult Silly Universe", None, "6969")},
            Volume: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                    1,
                )
            },
            TOTAL: 11,
        },
    }
)

CREATED_FK_METADATA_UPDATE_ALL = MappingProxyType(
    {
        CREATE_COMICS: {},
        DELETE_M2MS: {
            "characters": {(1, 1)},
            "identifiers": {(1, 1)},
            "locations": {(1, 1)},
            "series_groups": {(1, 1)},
            "story_arc_numbers": {(1, 4)},
            "tags": {(1, 2)},
        },
        FIS: {},
        LINK_FKS: {
            PATH: {
                "age_rating": ("Adult",),
                "country": ("GB",),
                "language": ("fr",),
                "original_format": ("Hardcover",),
                "protagonist": ("Team Cornish Game Hen",),
                "scan_info": ("Digital",),
            }
        },
        LINK_M2MS: {
            PATH: {
                "genres": {("Mystery",)},
                "identifiers": {
                    ("comicvine", "comic", "145265"),
                    ("metron", "comic", "999"),
                },
                "locations": {("Mars",)},
                "series_groups": {("adult comics",)},
                "stories": {("The End",)},
                "story_arc_numbers": {("g", 5)},
            }
        },
        UPDATE_COMICS: {
            1: {
                "collection_title": "The Big Omnibus Part 2",
                "critical_rating": Decimal("5.00"),
                "day": 20,
                "issue_number": Decimal("2.2"),
                "issue_suffix": "XXX",
                "metadata_mtime": datetime(
                    2025, 6, 15, 18, 13, 44, tzinfo=timezone.utc
                ),
                "monochrome": True,
                "month": 12,
                "name": "The Beginning; The End",
                "notes": (
                    "Tagged with comicbox dev on 1970-01-01T00:00:00 [Issue ID 145269] "
                    "urn:comicvine:4000-145265"
                ),
                "page_count": 0,
                "reading_direction": "rtl",
                "review": "Actually unreadable.",
                "summary": "Captain Science's many adult adventures",
                "year": 1951,
            }
        },
    }
)

CREATED_COMICS_METADATA = MappingProxyType(
    {
        FIS: {},
        LINK_M2MS: {
            PATH: {
                "characters": {("Boy Empirical",), ("Captain Science",)},
                "credits": {("Joe Orlando", "Writer"), ("Wally Wood", "Penciller")},
                "folders": PATH_PARENTS,
                "genres": {("Science Fiction",)},
                "identifiers": {("comicvine", "comic", "145269")},
                "locations": {("The Moon",)},
                "series_groups": {("science comics",)},
                "stories": {("The Beginning",)},
                "story_arc_numbers": {("c", None), ("d", 1), ("e", 3), ("f", 5)},
                "tags": {("a",), ("b",), ("c",)},
                "teams": {("Team Scientific Method",)},
                "universes": {("Young Adult Silly Universe",)},
            }
        },
        DELETE_M2MS: {},
    }
)
CREATED_COMICS_METADATA_UPDATE_ALL = MappingProxyType(
    {
        DELETE_M2MS: {
            "characters": {(1, 1)},
            "identifiers": {(1, 1)},
            "locations": {(1, 1)},
            "series_groups": {(1, 1)},
            "story_arc_numbers": {(1, 4)},
            "tags": {(1, 2)},
        },
        FIS: {},
        LINK_M2MS: {
            PATH: {
                "genres": {("Mystery",)},
                "identifiers": {
                    ("comicvine", "comic", "145265"),
                    ("metron", "comic", "999"),
                },
                "locations": {("Mars",)},
                "series_groups": {("adult comics",)},
                "stories": {("The End",)},
                "story_arc_numbers": {("g", 5)},
            }
        },
    }
)
LINKED_COMICS_METADATA = MappingProxyType({FIS: {}})
LINKED_COMICS_METADATA_UPDATE_ALL = MappingProxyType({FIS: {}})


def write_out(old_md, new_md):
    """Write out formatted dicts for diffing."""
    Path("old.py").write_text(pformat(old_md))
    Path("new.py").write_text(pformat(new_md))


def _diff_assert(old_md, new_md):
    diff = DeepDiff(old_md, new_md)
    if diff:
        pprint(diff)
        pprint(new_md)
        if os.environ.get("CODEX_TEST_IMPORT_WRITE"):
            write_out(old_md, new_md)
    assert not diff


class BaseTestImporter(SerializeMixin, TestCase, ABC):
    lockfile = __file__

    @override
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cache.clear()
        codex_init()
        TMP_DIR.mkdir(exist_ok=True)
        shutil.copy(COMIC_PATH, PATH)

    @override
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP_DIR)

    @override
    def setUp(self):
        cache.clear()
        Library.objects.create(path=LIBRARY_PATH)
        pk = Library.objects.get(path=LIBRARY_PATH).pk
        self.task = ImportTask(library_id=pk, files_modified=frozenset({PATH}))
        self.importer = ComicImporter(self.task, logger, LIBRARIAN_QUEUE, Event())

    @override
    def tearDown(self):
        super().tearDown()
        cache.clear()


class TestImporterBasic(BaseTestImporter):
    def test_import(self):
        # Extract and Aggregate
        self.importer.read()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(AGGREGATED_METADATA, md)

        # Query
        self.importer.query()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(QUERIED_METADATA, md)

        # Create Fks
        self.importer.create_all_fks()
        self.importer.update_all_fks()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(CREATED_FK_METADATA, md)
        assert Identifier.objects.count() == 3  # noqa: PLR2004

        # Create Comics
        self.importer.update_comics()
        self.importer.create_comics()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(CREATED_COMICS_METADATA, md)
        comic = Comic.objects.get(path=PATH)
        assert comic
        assert comic.year == 1950  # noqa: PLR2004

        # Link
        self.importer.metadata = dict(CREATED_COMICS_METADATA)
        self.importer.link_comic_m2m_fields()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(LINKED_COMICS_METADATA, md)
        comic = (
            Comic.objects.prefetch_related("characters", "folders")
            .only("characters", "folders")
            .get(path=PATH)
        )

        folder_paths = {folder.path for folder in comic.folders.all()}
        diff = folder_paths == FLAT_PATH_PARENTS
        if not diff:
            print(f"{folder_paths=} {FLAT_PATH_PARENTS=}")  # noqa: T201
        assert diff
        character_names = tuple(
            sorted(character.name for character in comic.characters.all())
        )
        diff = character_names == CHARACTER_NAMES
        if not diff:
            print(f"{character_names=} {CHARACTER_NAMES=}")  # noqa: T201
        assert diff


class BaseTestImporterUpdate(BaseTestImporter, ABC):
    @override
    def setUp(self):
        super().setUp()
        importer = ComicImporter(self.task, logger, LIBRARIAN_QUEUE, Event())
        importer.metadata = dict(QUERIED_METADATA)
        importer.create_and_update()
        importer.link()
        md = MappingProxyType(importer.metadata)
        _diff_assert(LINKED_COMICS_METADATA, md)
        comic = Comic.objects.get(path=PATH)
        assert comic


class TestImporterUpdateNone(BaseTestImporterUpdate):
    def test_update_none(self):
        self.importer.metadata = dict(AGGREGATED_METADATA)
        self.importer.query()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(QUERIED_METADATA_NONE, md)


class TestImporterUpdateAll(BaseTestImporterUpdate):
    @override
    def setUp(self):
        super().setUp()
        shutil.copy(UPDATE_PATH, PATH)

    def test_import(self):
        self.importer.read()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(AGGREGATED_METADATA_UPDATE_ALL, md)

        # Query
        self.importer.query()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(QUERIED_METADATA_UPDATE_ALL, md)

        # Create & Update Fks
        self.importer.create_all_fks()
        self.importer.update_all_fks()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(CREATED_FK_METADATA_UPDATE_ALL, md)
        assert Identifier.objects.count() == 15  # noqa: PLR2004

        # Create & Update Comics
        self.importer.update_comics()
        self.importer.create_comics()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(CREATED_COMICS_METADATA_UPDATE_ALL, md)
        comic = Comic.objects.get(path=PATH)
        assert comic

        # Link
        self.importer.link_comic_m2m_fields()
        md = MappingProxyType(self.importer.metadata)
        _diff_assert(LINKED_COMICS_METADATA_UPDATE_ALL, md)

        folder_paths = {folder.path for folder in comic.folders.all()}
        diff = folder_paths == FLAT_PATH_PARENTS
        if not diff:
            print(f"{folder_paths=} {FLAT_PATH_PARENTS=}")  # noqa: T201
        assert diff
        character_names = tuple(
            sorted(character.name for character in comic.characters.all())
        )
        diff = character_names == UPDATED_CHARACTER_NAMES
        if not diff:
            print(f"{character_names=} {UPDATED_CHARACTER_NAMES=}")  # noqa: T201
        assert diff
