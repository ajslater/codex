"""Test extract metadata importer."""

import os
import shutil
from abc import ABC
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from pprint import pformat, pprint
from threading import Event, Lock
from types import MappingProxyType

from deepdiff import DeepDiff
from django.core.cache import cache
from django.test import TestCase
from django.test.testcases import SerializeMixin
from loguru import logger
from typing_extensions import override

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.const import (
    COMIC_FK_FIELD_NAMES,
    COMIC_M2M_FIELD_NAMES,
    CREATE_COMICS,
    CREATE_FKS,
    DELETE_M2MS,
    FIS,
    FTS_CREATE,
    FTS_CREATED_M2MS,
    FTS_EXISTING_M2MS,
    FTS_UPDATE,
    FTS_UPDATED_M2MS,
    LINK_FKS,
    LINK_M2MS,
    QUERY_MODELS,
    TOTAL,
    UPDATE_COMICS,
    UPDATE_FKS,
)
from codex.librarian.scribe.importer.importer import ComicImporter
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
from codex.models.comic import ComicFTS
from codex.models.library import Library
from codex.startup import codex_init

TMP_DIR = Path("/tmp") / Path(__file__).stem  # noqa: S108
LIBRARY_PATH = TMP_DIR
FILES_DIR = Path(__file__).parent.parent / "files"
COMIC_PATH = FILES_DIR / "comicbox-2-example.cbz"
PATH = str(LIBRARY_PATH / "test.cbz")
PATH_PARENTS = {(str(Path(PATH).parent),)}
PATH_PARENTS_QUERY = {(str(Path(PATH).parent),): set()}
COMPLEX_FIELD_NAMES = frozenset({"credits", "story_arc_numbers", "identifiers"})
AGGREGATED = MappingProxyType(
    {
        FIS: {},
        QUERY_MODELS: {
            AgeRating: {("Everyone",): set()},
            # alternate_images ignored
            Character: {
                ("Captain Science",): {(None,)},
                ("Boy Empirical",): {(("metron", "character", "345"),)},
            },
            Folder: deepcopy(PATH_PARENTS_QUERY),
            Country: {("US",): set()},
            Credit: {
                ("Joe Orlando", "Writer"): set(),
                ("Wally Wood", "Penciller"): set(),
            },
            CreditPerson: {("Joe Orlando",): {(None,)}, ("Wally Wood",): {(None,)}},
            CreditRole: {("Penciller",): {(None,)}, ("Writer",): {(None,)}},
            # credit_primaries ignored
            Genre: {("Science Fiction",): {(None,)}},
            Language: {("en",): set()},
            Location: {("The Moon",): {(None,)}},
            OriginalFormat: {("Trade Paperback",): set()},
            Tag: {
                ("a",): {
                    (None,),
                },
                ("b",): {
                    (None,),
                },
                ("c",): {
                    (None,),
                },
            },
            Tagger: {("comicbox dev",): set()},
            Publisher: {("Youthful Adventure Stories",): {(None,)}},
            Imprint: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                ): {(None,)},
            },
            ScanInfo: {("Photocopied",): set()},
            Series: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                ): {
                    (None, None),
                }
            },
            SeriesGroup: {("science comics",): set()},
            Volume: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                ): {(7,)},
            },
            Team: {("Team Scientific Method",): {(None,)}},
            IdentifierSource: {("comicvine",): set(), ("metron",): set()},
            Identifier: {
                (
                    "comicvine",
                    "comic",
                    "145269",
                ): {
                    ("https://comicvine.gamespot.com/c/4000-145269/",),
                },
                ("metron", "character", "345"): {
                    ("https://metron.cloud/character/345",)
                },
                ("metron", "storyarc", "123"): {("https://metron.cloud/arc/123",)},
            },
            # prices future
            Story: {
                ("The Beginning",): {(None,)},
            },
            StoryArc: {
                ("c",): {(None,)},
                ("d",): {(("metron", "storyarc", "123"),)},
                ("e",): {(None,)},
                ("f",): {(None,)},
            },
            StoryArcNumber: {
                ("c", None): set(),
                ("d", 1): set(),
                ("e", 3): set(),
                ("f", 5): set(),
            },
            Universe: {("Young Adult Silly Universe",): {(None, "4242")}},
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
                "metadata_mtime": datetime(2025, 8, 6, 12, 29, 6, tzinfo=timezone.utc),
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
    },
)
QUERIED = MappingProxyType(
    {
        CREATE_COMICS: {
            PATH: {
                "collection_title": "The Big Omnibus",
                "critical_rating": Decimal("10.00"),
                "day": 1,
                "file_type": "CBZ",
                "issue_number": Decimal("1.2"),
                "issue_suffix": "S",
                "metadata_mtime": datetime(2025, 8, 6, 12, 29, 6, tzinfo=timezone.utc),
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
        FTS_EXISTING_M2MS: {},
    }
)
CREATED_FK = MappingProxyType(
    {
        CREATE_COMICS: {
            PATH: {
                "collection_title": "The Big Omnibus",
                "critical_rating": Decimal("10.00"),
                "day": 1,
                "file_type": "CBZ",
                "issue_number": Decimal("1.2"),
                "issue_suffix": "S",
                "metadata_mtime": datetime(2025, 8, 6, 12, 29, 6, tzinfo=timezone.utc),
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
        FTS_EXISTING_M2MS: {},
        FTS_UPDATED_M2MS: {},
        FTS_CREATED_M2MS: {"universes": {("Young Adult Silly Universe",): ("4242",)}},
    }
)
CREATED_COMICS = MappingProxyType(
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
        FTS_CREATE: {
            1: {
                "age_rating": ("Everyone",),
                "collection_title": ("The Big Omnibus",),
                "country": ("US",),
                "imprint": ("TestImprint",),
                "language": ("en",),
                "name": ("The Beginning",),
                "original_format": ("Trade Paperback",),
                "publisher": ("Youthful Adventure Stories",),
                "review": ("It wasn't all bad.",),
                "scan_info": ("Photocopied",),
                "series": ("Captain Science",),
                "summary": ("Captain Science's many scientific adventures",),
                "tagger": ("comicbox dev",),
            }
        },
        FTS_UPDATED_M2MS: {},
        FTS_EXISTING_M2MS: {},
        FTS_CREATED_M2MS: {"universes": {("Young Adult Silly Universe",): ("4242",)}},
    }
)
LINKED_COMICS = MappingProxyType(
    {
        FIS: {},
        FTS_CREATE: {
            1: {
                "age_rating": ("Everyone",),
                "characters": ("Boy Empirical", "Captain Science"),
                "collection_title": ("The Big Omnibus",),
                "country": ("US",),
                "credits": ("Joe Orlando", "Wally Wood"),
                "genres": ("Science Fiction",),
                "imprint": ("TestImprint",),
                "language": ("en",),
                "locations": ("The Moon",),
                "name": ("The Beginning",),
                "original_format": ("Trade Paperback",),
                "publisher": ("Youthful Adventure Stories",),
                "review": ("It wasn't all bad.",),
                "scan_info": ("Photocopied",),
                "series": ("Captain Science",),
                "series_groups": ("science comics",),
                "sources": ("comicvine",),
                "stories": ("The Beginning",),
                "story_arcs": ("c", "d", "e", "f"),
                "summary": ("Captain Science's many scientific adventures",),
                "tagger": ("comicbox dev",),
                "tags": ("a", "b", "c"),
                "teams": ("Team Scientific Method",),
                "universes": (
                    "4242",
                    "Young Adult Silly Universe",
                ),
            },
        },
        FTS_EXISTING_M2MS: {},
        FTS_CREATED_M2MS: {"universes": {}},
        FTS_UPDATED_M2MS: {},
    }
)

FAILED_IMPORTS = MappingProxyType(
    {
        FTS_CREATE: {
            1: {
                "age_rating": ("Everyone",),
                "characters": ("Boy Empirical", "Captain Science"),
                "collection_title": ("The Big Omnibus",),
                "country": ("US",),
                "credits": ("Joe Orlando", "Wally Wood"),
                "genres": ("Science Fiction",),
                "imprint": ("TestImprint",),
                "language": ("en",),
                "locations": ("The Moon",),
                "name": ("The Beginning",),
                "original_format": ("Trade Paperback",),
                "publisher": ("Youthful Adventure Stories",),
                "review": ("It wasn't all bad.",),
                "scan_info": ("Photocopied",),
                "series": ("Captain Science",),
                "series_groups": ("science comics",),
                "sources": ("comicvine",),
                "stories": ("The Beginning",),
                "story_arcs": ("c", "d", "e", "f"),
                "summary": ("Captain Science's many scientific adventures",),
                "tagger": ("comicbox dev",),
                "tags": ("a", "b", "c"),
                "teams": ("Team Scientific Method",),
                "universes": (
                    "4242",
                    "Young Adult Silly Universe",
                ),
            },
        },
        FTS_EXISTING_M2MS: {},
        FTS_UPDATED_M2MS: {},
        FTS_CREATED_M2MS: {"universes": {}},
    }
)
DELETED_COMICS = MappingProxyType(
    {
        FTS_CREATE: {
            1: {
                "age_rating": ("Everyone",),
                "characters": ("Boy Empirical", "Captain Science"),
                "collection_title": ("The Big Omnibus",),
                "country": ("US",),
                "credits": ("Joe Orlando", "Wally Wood"),
                "genres": ("Science Fiction",),
                "imprint": ("TestImprint",),
                "language": ("en",),
                "locations": ("The Moon",),
                "name": ("The Beginning",),
                "original_format": ("Trade Paperback",),
                "publisher": ("Youthful Adventure Stories",),
                "review": ("It wasn't all bad.",),
                "scan_info": ("Photocopied",),
                "series": ("Captain Science",),
                "series_groups": ("science comics",),
                "sources": ("comicvine",),
                "stories": ("The Beginning",),
                "story_arcs": ("c", "d", "e", "f"),
                "summary": ("Captain Science's many scientific adventures",),
                "tagger": ("comicbox dev",),
                "tags": ("a", "b", "c"),
                "teams": ("Team Scientific Method",),
                "universes": (
                    "4242",
                    "Young Adult Silly Universe",
                ),
            },
        },
        FTS_EXISTING_M2MS: {},
        FTS_UPDATED_M2MS: {},
        FTS_CREATED_M2MS: {"universes": {}},
    }
)
FTSED = MappingProxyType({})
_FK_VALUE_POS = MappingProxyType(
    {
        "volume": -2,
    }
)
_COMPLEX_KEYS = frozenset({"credits", "identifiers", "story_arc_numbers"})
_COMICFTS_IGNORE_KEYS = ("comic_id", "updated_at", "created_at")


def create_fts_strings(md, pk):
    """Create the fts values for comparison from the md."""
    fts_md = {}
    for key in (FTS_CREATE, FTS_UPDATE):
        for field_name, values in md.get(key, {}).get(pk, {}).items():
            all_values = values + md[FTS_EXISTING_M2MS].get(pk, {}).get(field_name, ())
            fts_md[field_name] = ",".join(sorted(all_values))
    return fts_md


FTS_FINAL_BASIC = MappingProxyType(
    {
        **create_fts_strings(LINKED_COMICS, 1),
        "country": "US,United States",
        "language": "en,English",
        "sources": "Comic Vine,comicvine",
    }
)


def create_compare_comic_values(agg_md):
    """Create the comic values for comparison from the aggregate md."""
    comic = {**agg_md[CREATE_COMICS][PATH]}
    for key, values in agg_md[LINK_FKS][PATH].items():
        pos = _FK_VALUE_POS.get(key, -1)
        comic[key] = values[pos]
    for key, values in agg_md[LINK_M2MS][PATH].items():
        if key in _COMPLEX_KEYS:
            final_val = tuple(sorted(values))
        elif key == "folders":
            final_val = tuple(sorted(Path(val[0]).name for val in values))
        else:
            final_val = tuple(sorted(val[0] for val in values))
        comic[key] = final_val
    comic.pop("protagonist", None)

    return MappingProxyType(comic)


COMIC_VALUES_BASIC = create_compare_comic_values(AGGREGATED)


def write_out(old_md, new_md):
    """Write out formatted dicts for diffing."""
    Path("old.py").write_text(pformat(old_md))
    Path("new.py").write_text(pformat(new_md))


def diff_assert(old_md: Mapping, new_md: Mapping, phase: str):
    """Assert a deep diff."""
    if diff := DeepDiff(old_md, new_md):
        print("Test Phase:", phase)  # noqa: T201
        pprint(diff)
        pprint(new_md)
        if os.environ.get("CODEX_TEST_IMPORT_WRITE"):
            write_out(old_md, new_md)
    assert not diff


def _test_comic_creation_field_protagonist(comic, field_name, test_value):
    diff = (comic.main_character and test_value == comic.main_character.name) or (
        comic.main_team and test_value == comic.main_team.name
    )
    if not diff:
        print(  # noqa: T201
            f"{field_name}:{test_value} == {comic.main_character=} or {comic.main_team=}"
        )
    assert diff


def _test_comic_creation_field_complex(field_name: str, value):
    if field_name == "credits":
        value = tuple(
            sorted((subval.person.name, subval.role.name) for subval in value.all())
        )
    elif field_name == "story_arc_numbers":
        value = tuple(
            sorted((subval.story_arc.name, subval.number) for subval in value.all())
        )
    elif field_name == "identifiers":
        value = tuple(
            sorted(
                (subval.source.name, subval.id_type, subval.key)
                for subval in value.all()
            )
        )
    return value


def _test_comic_creation_field(comic, field_name, test_value):
    if field_name == "protagonist":
        _test_comic_creation_field_protagonist(comic, field_name, test_value)
        return
    value = getattr(comic, field_name)

    if field_name in COMIC_FK_FIELD_NAMES:
        value = value.name
    elif field_name in COMPLEX_FIELD_NAMES:
        value = _test_comic_creation_field_complex(field_name, value)
    elif field_name in COMIC_M2M_FIELD_NAMES:
        value = tuple(sorted(subval.name for subval in value.all()))
    diff = test_value == value
    if not diff:
        print(f"{field_name} {test_value=} {value=}")  # noqa: T201
    assert diff


def test_comic_creation(values_const: MappingProxyType):
    """Test Comic Creation and Linking."""
    qs = Comic.objects.prefetch_related(*COMIC_M2M_FIELD_NAMES).select_related(
        *COMIC_FK_FIELD_NAMES, "main_team", "main_character"
    )
    comic = qs.get(path=PATH)
    # values = qs.filter(path=PATH).values().first() debug
    # ic(values) debug

    for field_name, test_value in values_const.items():
        _test_comic_creation_field(comic, field_name, test_value)
    return comic


def test_fts_creation(values_const: MappingProxyType, comic: Comic):
    """FTS Values."""
    qs = ComicFTS.objects.filter(comic_id=comic.pk).values()
    comicfts = qs[0]
    fts_values = deepcopy(dict(values_const))
    for key in _COMICFTS_IGNORE_KEYS:
        comicfts.pop(key)
    diff_assert(fts_values, comicfts, "COMIC_FTS")


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
        self.importer = ComicImporter(
            self.task, logger, LIBRARIAN_QUEUE, Lock(), Event()
        )

    @override
    def tearDown(self):
        super().tearDown()
        cache.clear()


class TestImporterBasic(BaseTestImporter):
    def test_import(self):
        # Extract and Aggregate
        self.importer.read()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(AGGREGATED, md, "AGGREGATED")

        # Query
        self.importer.query()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(QUERIED, md, "QUERIED")

        # Create Fks
        self.importer.create_all_fks()
        self.importer.update_all_fks()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(CREATED_FK, md, "CREATED_FK")
        assert Identifier.objects.count() == 3  # noqa: PLR2004

        # Create Comics
        self.importer.update_comics()
        self.importer.create_comics()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(CREATED_COMICS, md, "CREATED_COMICS")
        comic = Comic.objects.get(path=PATH)
        assert comic
        assert comic.year == 1950  # noqa: PLR2004

        # Link
        self.importer.link()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(LINKED_COMICS, md, "LINKED_COMICS")

        # Fail imports
        self.importer.fail_imports()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(FAILED_IMPORTS, md, "FAILED_IMPORTS")

        # Delete
        self.importer.delete()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(DELETED_COMICS, md, "DELETED_COMICS")
        comic = test_comic_creation(COMIC_VALUES_BASIC)

        # FTS
        self.importer.full_text_search()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(FTSED, md, "FTSED")

        test_fts_creation(FTS_FINAL_BASIC, comic)
