"""Locking, Aliasing Xapian Backend."""
from django.utils.timezone import now
from haystack.backends import UnifiedIndex
from haystack.backends.whoosh_backend import TEXT, WhooshEngine, WhooshSearchBackend
from humanfriendly import InvalidSize, parse_size
from whoosh.analysis import CharsetFilter, Filter
from whoosh.fields import NUMERIC
from whoosh.qparser import FieldAliasPlugin, GtLtPlugin
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.support.charset import accent_map

from codex.search.search_indexes import ComicIndex
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class CodexUnifiedIndex(UnifiedIndex):
    """Custom Codex Unified Index."""

    def collect_indexes(self):
        """Replace auto app.search_index finding with one exact instance."""
        # Because i moved search_indexes into codex.search
        return [ComicIndex()]


def gen_multipart_field_aliases(field):
    bits = field.split("_")
    aliases = [field[:-1]]
    for connector in ("", "-"):
        joined = connector.join(bits)
        aliases += [joined, joined[:-1]]
    return aliases


class SizeFilter(Filter):

    # is_morph = True

    def __call__(self, tokens):
        print("SIZE_FILTER", tokens)
        for t in tokens:
            try:
                if t.mode == "query":
                    t.text = str(parse_size(t.text.lower()))
                    print("SIZE FILTER", t.original, "=>", t.text)
            except InvalidSize as exc:
                LOG.debug(exc)
                t.text = ""
            except Exception as exc:
                LOG.exception(exc)
                t.text = ""
            yield t


class FILESIZE(NUMERIC):
    def __init__(
        self,
        numtype=int,
        bits=32,
        stored=False,
        unique=False,
        field_boost=1.0,
        decimal_places=0,
        shift_step=4,
        signed=True,
        sortable=False,
        default=None,
    ):
        super().__init__(
            numtype=numtype,
            bits=bits,
            stored=stored,
            unique=unique,
            field_boost=field_boost,
            decimal_places=decimal_places,
            shift_step=shift_step,
            signed=signed,
            sortable=sortable,
            default=default,
        )
        self.analyzer |= SizeFilter()

    @staticmethod
    def _parse_size(value):
        try:
            value = str(parse_size(value))
        except InvalidSize as exc:
            LOG.debug(exc)
        return value

    def parse_query(self, fieldname, qstring, boost=1.0):
        qstring = self._parse_size(qstring)
        return super().parse_query(fieldname, qstring, boost=boost)

    def parse_range(self, fieldname, start, end, startexcl, endexcl, boost=1.0):
        if start:
            start = self._parse_size(start)
        if end:
            end = self._parse_size(end)
        return super().parse_range(
            fieldname, start, end, startexcl, endexcl, boost=boost
        )


class CodexSearchBackend(WhooshSearchBackend):
    FIELDMAP = {
        "characters": ["category", "character"],
        "created_at": ["created"],
        "creators": ["author", "authors", "contributor", "contributors", "creator"],
        "genres": ["genre"],
        "locations": ["location"],
        "name": ["title"],
        "read_ltr": ["ltr"],
        "series_groups": gen_multipart_field_aliases("series_groups"),
        "scan_info": ["scan"],
        "story_arcs": gen_multipart_field_aliases("story_arcs"),
        "tags": ["tag"],
        "teams": ["team"],
        "updated_at": ["updated"],
    }
    RESERVED_CHARACTERS = ()
    RESERVED_WORDS = ()

    def build_schema(self, fields):
        content_field_name, schema = super().build_schema(fields)

        for _, field in schema.items():
            if isinstance(field, TEXT):
                field.analyzer |= CharsetFilter(accent_map)
        old_field = schema["size"]
        schema.remove("size")
        schema.add(
            "size",
            FILESIZE(
                stored=old_field.stored,
                numtype=old_field.numtype,
                field_boost=old_field.format.field_boost,
            ),
        )

        return (content_field_name, schema)

    def setup(self):
        super().setup()
        self.parser.add_plugins(
            (
                FieldAliasPlugin(self.FIELDMAP),
                GtLtPlugin,
                # RegexPlugin,  # not working yet
                DateParserPlugin(basedate=now()),
            )
        )


class CodexSearchEngine(WhooshEngine):
    """A search engine with a locking backend."""

    backend = CodexSearchBackend
    unified_index = CodexUnifiedIndex
