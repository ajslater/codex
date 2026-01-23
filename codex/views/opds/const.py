"""OPDS Common consts."""

from types import MappingProxyType

from codex.models import (
    Character,
    Genre,
    Location,
    SeriesGroup,
    StoryArc,
    Tag,
    Team,
)

BLANK_TITLE = "(Empty)"
AUTHOR_ROLES = {"Writer", "Author", "Script", "Plot", "Plotter", "Scripter"}
OPDS_M2M_MODELS = (Character, Genre, Location, SeriesGroup, StoryArc, Tag, Team)


class BookmarkFilters:
    """Bookmark Filters."""

    UNREAD = MappingProxyType({"bookmark": "UNREAD"})
    IN_PROGRESS = MappingProxyType({"bookmark": "IN_PROGRESS"})
    READ = MappingProxyType({"bookmark": "READ"})
    NONE = MappingProxyType({"bookmark": ""})


DEFAULT_PARAMS = MappingProxyType(
    {
        "top_group": "p",
        "filters": {"bookmark": BookmarkFilters.NONE},
        "order_by": "sort_name",
        "order_reverse": False,
        "show": {"p": True, "s": True},
    }
)


class Rel:
    """Link rel strings."""

    AUTHENTICATION = "http://opds-spec.org/auth/document"
    FACET = "http://opds-spec.org/facet"
    ACQUISITION = "http://opds-spec.org/acquisition"
    THUMBNAIL = "http://opds-spec.org/image/thumbnail"
    IMAGE = "http://opds-spec.org/image"
    STREAM = "http://vaemendis.net/opds-pse/stream"
    SORT_NEW = "http://opds-spec.org/sort/new"
    POPULAR = "http://opds-spec.org/sort/popular"
    FEATURED = "http://opds-spec.org/featured"
    PROGRESSION = "http://www.cantook.com/api/progression"
    SELF = "self"
    START = "start"
    UP = "up"
    PREV = "previous"
    NEXT = "next"
    ALTERNATE = "alternate"
    SUB = "subsection"
    SEARCH = "search"
    REGISTER = "register"
    FIRST = "first"
    LAST = "last"
    TOP = "top"


class MimeType:
    """Mime Types."""

    ATOM = "application/atom+xml"
    _PROFILE_CATALOG = "profile=opds-catalog"
    DIVINA = "application/divina+json"
    NAV = f"{ATOM};{_PROFILE_CATALOG};kind=navigation"
    ACQUISITION = f"{ATOM};{_PROFILE_CATALOG};kind=acquisition"
    ENTRY_CATALOG = f"{ATOM};type=entry;{_PROFILE_CATALOG}"
    AUTHENTICATION = "application/opds-authentication+json"
    OPENSEARCH = "application/opensearchdescription+xml"
    STREAM = "image/jpeg"
    OPDS_JSON = "application/opds+json"
    OPDS_PUB = "application/opds-publication+json"
    PROGRESSION = "application/vnd.readium.progression+json"
    BOOK = "http://schema.org/Book"
    # COMIC = "https://schema.org/ComicStory" unused
    JPEG = "image/jpeg"
    WEBP = "image/webp"
    HTML = "text/html"
    AUTH_BASIC = "http://opds-spec.org/auth/basic"
    COOKIE = "cookie"
    FILE_TYPE_MAP: MappingProxyType[str, str] = MappingProxyType(
        {
            "CBZ": "application/vnd.comicbook+zip",
            "CBR": "application/vnd.comicbook+rar",
            "CBT": "application/vnd.comicbook+tar",
            "CB7": "application/vnd.comicbook+7zip",
            "PDF": "application/pdf",
        }
    )
    SIMPLE_FILE_TYPE_MAP: MappingProxyType[str, str] = MappingProxyType(
        {
            # PocketBooks needs app/zip
            "CBZ": "application/zip",
            "CBR": "application/x-rar-compressed",
            "CBT": "application/x-tar",
            "CB7": "application/x-7z-compressed",
            "PDF": "application/pdf",
        }
    )
    OCTET = "application/octet-stream"


class UserAgentNames:
    """Control whether to hack in facets with nav links."""

    CLIENT_REORDERS = frozenset({"Chunky"})
    FACET_SUPPORT = frozenset({"yar"})  # kybooks
    SIMPLE_DOWNLOAD_MIME_TYPES = frozenset({"PocketBook Reader"})
    REQUIRE_ABSOLUTE_URL = frozenset()


class TopRoutes:
    """Routes for top groups."""

    ROOT = MappingProxyType({"group": "r", "pks": (0,), "page": 1})
    PUBLISHER = MappingProxyType({**ROOT, "group": "p"})
    SERIES = MappingProxyType({**ROOT, "group": "s"})
    FOLDER = MappingProxyType({**ROOT, "group": "f"})
    STORY_ARC = MappingProxyType({**ROOT, "group": "a"})
