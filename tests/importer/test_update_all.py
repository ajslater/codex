"""Test extract metadata importer."""

import shutil
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType

from typing_extensions import override

from codex.librarian.scribe.importer.const import (
    CREATE_COMICS,
    CREATE_FKS,
    DELETE_M2MS,
    FIS,
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
    Universe,
    Volume,
)
from tests.importer.test_basic import (
    COMIC_VALUES_BASIC,
    FTS_FINAL_BASIC,
    PATH,
    PATH_PARENTS,
    PATH_PARENTS_QUERY,
    create_compare_comic_values,
    create_fts_strings,
    diff_assert,
    test_comic_creation,
    test_fts_creation,
)
from tests.importer.test_update_none import UPDATE_PATH, BaseTestImporterUpdate

AGGREGATED_UPDATE_ALL = MappingProxyType(
    {
        CREATE_COMICS: {
            PATH: {
                "collection_title": "The Big Omnibus Part 2",
                "critical_rating": Decimal("5.00"),
                "day": 20,
                "issue_number": Decimal("2.2"),
                "issue_suffix": "XXX",
                "metadata_mtime": datetime(2025, 8, 6, 12, 37, 6, tzinfo=timezone.utc),
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
            IdentifierSource: {("comicvine",): set(), ("metron",): set()},
            Identifier: {
                ("comicvine", "comic", "145265"): {
                    ("https://comicvine.gamespot.com/c/4000-145265/",),
                },
                ("comicvine", "location", "111"): {
                    ("https://comicvine.gamespot.com/c/4020-111/",),
                },
                ("comicvine", "series", "333"): {
                    ("https://comicvine.gamespot.com/c/4050-333/",),
                },
                ("comicvine", "storyarc", "456"): {
                    ("https://comicvine.gamespot.com/c/4045-456/",),
                },
                ("comicvine", "storyarc", "890"): {
                    ("https://comicvine.gamespot.com/c/4045-890/",),
                },
                (
                    "metron",
                    "character",
                    "123",
                ): {
                    ("https://metron.cloud/character/123",),
                },
                ("metron", "comic", "999"): {
                    ("https://metron.cloud/issue/999",),
                },
                ("metron", "creditperson", "123"): {
                    ("https://metron.cloud/creator/123",),
                },
                ("metron", "genre", "012"): {
                    ("https://metron.cloud/genre/012",),
                },
                ("metron", "imprint", "123"): {
                    ("https://metron.cloud/imprint/123",),
                },
                ("metron", "publisher", "111"): {
                    ("https://metron.cloud/publisher/111",),
                },
                ("metron", "story", "555"): {
                    ("https://metron.cloud/story/555",),
                },
            },
            Publisher: {
                ("Youthful Adventure Stories",): {
                    (("metron", "publisher", "111"),),
                }
            },
            Imprint: {
                ("Youthful Adventure Stories", "TestImprint"): {
                    (("metron", "imprint", "123"),),
                }
            },
            Series: {
                ("Youthful Adventure Stories", "TestImprint", "Captain Science"): {
                    (
                        ("comicvine", "series", "333"),
                        None,
                    ),
                }
            },
            Language: {("fr",): set()},
            Volume: {
                (
                    "Youthful Adventure Stories",
                    "TestImprint",
                    "Captain Science",
                    1950,
                    None,
                ): {
                    (1,),
                }
            },
            Folder: deepcopy(PATH_PARENTS_QUERY),
            AgeRating: {("Adult",): set()},
            Character: {
                ("Captain Science",): {
                    (("metron", "character", "123"),),
                }
            },
            CreditPerson: {
                ("Joe Orlando",): {
                    (("metron", "creditperson", "123"),),
                },
                ("Wally Wood",): {
                    (None,),
                },
            },
            CreditRole: {
                ("Penciller",): {
                    (None,),
                },
                ("Writer",): {
                    (None,),
                },
            },
            Credit: {
                ("Joe Orlando", "Writer"): set(),
                ("Wally Wood", "Penciller"): set(),
            },
            Country: {("GB",): set()},
            Genre: {
                ("Mystery",): {
                    (None,),
                },
                ("Science Fiction",): {
                    (("metron", "genre", "012"),),
                },
            },
            Location: {
                ("Mars",): {
                    (("comicvine", "location", "111"),),
                }
            },
            OriginalFormat: {("Hardcover",): set()},
            ScanInfo: {("Digital",): set()},
            SeriesGroup: {("adult comics",): set()},
            Story: {
                ("The Beginning",): {
                    (("metron", "story", "555"),),
                },
                ("The End",): {
                    (None,),
                },
            },
            StoryArc: {
                ("c",): {
                    (None,),
                },
                ("d",): {
                    (("comicvine", "storyarc", "890"),),
                },
                ("e",): {
                    (("comicvine", "storyarc", "456"),),
                },
                ("g",): {
                    (None,),
                },
            },
            StoryArcNumber: {
                ("c", None): set(),
                ("d", 1): set(),
                ("e", 3): set(),
                ("g", 5): set(),
            },
            Tag: {
                ("a",): {
                    (None,),
                },
                ("c",): {
                    (None,),
                },
            },
            Tagger: {("comicbox dev",): set()},
            Universe: {
                ("Young Adult Silly Universe",): {
                    (None, "6969"),
                }
            },
        },
    }
)
QUERIED_UPDATE_ALL = MappingProxyType(
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
        FTS_EXISTING_M2MS: {
            1: {
                "characters": ("Captain Science",),
                "genres": ("Science Fiction",),
                "stories": ("The Beginning",),
                "story_arcs": ("c", "d", "e"),
                "tags": ("a", "c"),
            }
        },
        LINK_M2MS: {
            PATH: {
                "genres": {
                    ("Mystery",),
                },
                "identifiers": {
                    ("metron", "comic", "999"),
                    ("comicvine", "comic", "145265"),
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
                "metadata_mtime": datetime(2025, 8, 6, 12, 37, 6, tzinfo=timezone.utc),
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

CREATED_FK_UPDATE_ALL = MappingProxyType(
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
        FTS_EXISTING_M2MS: {
            1: {
                "characters": ("Captain Science",),
                "genres": ("Science Fiction",),
                "stories": ("The Beginning",),
                "story_arcs": ("c", "d", "e"),
                "tags": ("a", "c"),
            }
        },
        LINK_M2MS: {
            PATH: {
                "genres": {
                    ("Mystery",),
                },
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
                "metadata_mtime": datetime(2025, 8, 6, 12, 37, 6, tzinfo=timezone.utc),
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
        FTS_UPDATED_M2MS: {"universes": {1}},
        FTS_CREATED_M2MS: {},
    }
)
CREATED_COMICS_UPDATE_ALL = MappingProxyType(
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
        FTS_EXISTING_M2MS: {
            1: {
                "characters": ("Captain Science",),
                "genres": ("Science Fiction",),
                "stories": ("The Beginning",),
                "story_arcs": ("c", "d", "e"),
                "tags": ("a", "c"),
            }
        },
        LINK_M2MS: {
            PATH: {
                "genres": {
                    ("Mystery",),
                },
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
        FTS_UPDATE: {
            1: {
                "age_rating": ("Adult",),
                "collection_title": ("The Big Omnibus Part 2",),
                "country": ("GB",),
                "language": ("fr",),
                "name": ("The Beginning; The End",),
                "original_format": ("Hardcover",),
                "review": ("Actually unreadable.",),
                "scan_info": ("Digital",),
                "summary": ("Captain Science's many adult adventures",),
            }
        },
        FTS_UPDATED_M2MS: {"universes": {1}},
        FTS_CREATED_M2MS: {},
    }
)
LINKED_COMICS_UPDATE_ALL = MappingProxyType(
    {
        FIS: {},
        FTS_EXISTING_M2MS: {
            1: {
                "characters": ("Captain Science",),
                "genres": ("Science Fiction",),
                "stories": ("The Beginning",),
                "story_arcs": ("c", "d", "e"),
                "tags": ("a", "c"),
            }
        },
        FTS_UPDATE: {
            1: {
                "age_rating": ("Adult",),
                "collection_title": ("The Big Omnibus Part 2",),
                "country": ("GB",),
                "genres": ("Mystery",),
                "language": ("fr",),
                "locations": ("Mars",),
                "name": ("The Beginning; The End",),
                "original_format": ("Hardcover",),
                "review": ("Actually unreadable.",),
                "scan_info": ("Digital",),
                "series_groups": ("adult comics",),
                "sources": ("comicvine", "metron"),
                "stories": ("The End",),
                "story_arcs": ("g",),
                "summary": ("Captain Science's many adult adventures",),
            }
        },
        FTS_UPDATED_M2MS: {"universes": {1}},
        FTS_CREATED_M2MS: {},
    }
)
FAILED_IMPORTS_UPDATE_ALL = MappingProxyType(
    {
        FTS_CREATED_M2MS: {},
        FTS_EXISTING_M2MS: {
            1: {
                "characters": ("Captain Science",),
                "genres": ("Science Fiction",),
                "stories": ("The Beginning",),
                "story_arcs": ("c", "d", "e"),
                "tags": ("a", "c"),
            }
        },
        FTS_UPDATE: {
            1: {
                "age_rating": ("Adult",),
                "collection_title": ("The Big Omnibus Part 2",),
                "country": ("GB",),
                "genres": ("Mystery",),
                "language": ("fr",),
                "locations": ("Mars",),
                "name": ("The Beginning; The End",),
                "original_format": ("Hardcover",),
                "review": ("Actually unreadable.",),
                "scan_info": ("Digital",),
                "series_groups": ("adult comics",),
                "sources": ("comicvine", "metron"),
                "stories": ("The End",),
                "story_arcs": ("g",),
                "summary": ("Captain Science's many adult adventures",),
            }
        },
        FTS_UPDATED_M2MS: {"universes": {1}},
    }
)
DELETED_COMICS_UPDATE_ALL = MappingProxyType(
    {
        FTS_CREATED_M2MS: {},
        FTS_EXISTING_M2MS: {
            1: {
                "characters": ("Captain Science",),
                "genres": ("Science Fiction",),
                "stories": ("The Beginning",),
                "story_arcs": ("c", "d", "e"),
                "tags": ("a", "c"),
            }
        },
        FTS_UPDATE: {
            1: {
                "age_rating": ("Adult",),
                "collection_title": ("The Big Omnibus Part 2",),
                "country": ("GB",),
                "genres": ("Mystery",),
                "language": ("fr",),
                "locations": ("Mars",),
                "name": ("The Beginning; The End",),
                "original_format": ("Hardcover",),
                "review": ("Actually unreadable.",),
                "scan_info": ("Digital",),
                "series_groups": ("adult comics",),
                "sources": ("comicvine", "metron"),
                "stories": ("The End",),
                "story_arcs": ("g",),
                "summary": ("Captain Science's many adult adventures",),
            }
        },
        FTS_UPDATED_M2MS: {"universes": {1}},
    }
)
FTSED_UPDATE_ALL = MappingProxyType({})
_FK_VALUE_POS = MappingProxyType(
    {
        "volume": -2,
    }
)
_COMPLEX_KEYS = frozenset({"credits", "identifiers", "story_arc_numbers"})
_COMICFTS_IGNORE_KEYS = ("comic_id", "updated_at", "created_at")

FTS_FINAL_UPDATE_ALL = MappingProxyType(
    {
        **FTS_FINAL_BASIC,
        **create_fts_strings(LINKED_COMICS_UPDATE_ALL, 1),
        "country": "GB,United Kingdom",
        "language": "fr,French",
        "sources": "Comic Vine,Metron,comicvine,metron",
        "universes": "6969,Young Adult Silly Universe",
        "characters": "Captain Science",
        "tags": "a,c",
    }
)

_COMIC_VALUES_UPDATE_ALL = create_compare_comic_values(AGGREGATED_UPDATE_ALL)
COMIC_VALUES_UPDATE_ALL = MappingProxyType(
    {**COMIC_VALUES_BASIC, **_COMIC_VALUES_UPDATE_ALL}
)


class TestImporterUpdateAll(BaseTestImporterUpdate):
    @override
    def setUp(self):
        super().setUp()
        shutil.copy(UPDATE_PATH, PATH)

    def test_update_all(self):
        self.importer.read()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(AGGREGATED_UPDATE_ALL, md, "AGGREGATED_UPDATE_ALL")

        # Query
        self.importer.query()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(QUERIED_UPDATE_ALL, md, "QUERIED_UPDATE_ALL")

        # Create & Update Fks
        self.importer.create_all_fks()
        self.importer.update_all_fks()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(CREATED_FK_UPDATE_ALL, md, "CREATED_FK_UPDATE_ALL")
        assert Identifier.objects.count() == 15  # noqa: PLR2004

        # Create & Update Comics
        self.importer.update_comics()
        self.importer.create_comics()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(CREATED_COMICS_UPDATE_ALL, md, "CREATED_COMICS_UPDATE_ALL")
        comic = Comic.objects.get(path=PATH)
        assert comic

        # Link
        self.importer.link_comic_m2m_fields()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(LINKED_COMICS_UPDATE_ALL, md, "LINKED_COMICS_UPDATE_ALL")

        comic = test_comic_creation(COMIC_VALUES_UPDATE_ALL)

        # Fail imports
        self.importer.fail_imports()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(FAILED_IMPORTS_UPDATE_ALL, md, "FAILED_IMPORTS_UPDATE_ALL")

        # Delete
        self.importer.delete()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(DELETED_COMICS_UPDATE_ALL, md, "DELETED_COMICS_UPDATE_ALL")

        # FTS
        self.importer.full_text_search()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(FTSED_UPDATE_ALL, md, "FTSED_UPDATE_ALL")
        test_fts_creation(FTS_FINAL_UPDATE_ALL, comic)
