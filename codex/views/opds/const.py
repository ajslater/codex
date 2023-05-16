"""OPDS Common consts."""

BLANK_TITLE = "Unknown"
FALSY = {"", "false", "0"}
AUTHOR_ROLES = {"Writer"}


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
    NAV = ";".join((ATOM, _PROFILE_CATALOG, "kind=navigation"))
    ACQUISITION = ";".join((ATOM, _PROFILE_CATALOG, "kind=acquisition"))
    ENTRY_CATALOG = ";".join((ATOM, "type=entry", _PROFILE_CATALOG))
    AUTHENTICATION = "application/opds-authentication+json"
    OPENSEARCH = "application/opensearchdescription+xml"
    STREAM = "image/jpeg"
    OPDS_JSON = "application/opds+json"
    OPDS_PUB = "application/opds-publication+json"
    BOOK = "http://schema.org/Book"
    # COMIC = "https://schema.org/ComicStory"
    JPEG = "image/jpeg"
    WEBP = "image/webp"
    HTML = "text/html"
    AUTH_BASIC = "http://opds-spec.org/auth/basic"
    COOKIE = "cookie"
    FILE_TYPE_MAP = {
        "CBZ": "application/vnd.comicbook+zip",
        "CBR": "application/vnd.comicbook+rar",
        "CBT": "application/vnd.comicbook+tar",
        "PDF": "application/pdf",
    }
    SIMPLE_FILE_TYPE_MAP = {
        # PocketBooks needs app/zip
        "CBZ": "application/zip",
        "CBR": "application/x-rar-compressed",
        "CBT": "application/x-tar",
        "PDF": "application/pdf",
    }
    OCTET = "application/octet-stream"
