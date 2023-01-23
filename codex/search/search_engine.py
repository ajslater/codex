"""Locking, Aliasing Xapian Backend."""
from django.utils.timezone import now
from haystack.backends import UnifiedIndex
from haystack.backends.whoosh_backend import (
    TEXT,
    WhooshEngine,
    WhooshSearchBackend,
    WhooshSearchQuery,
)
from humanfriendly import InvalidSize, parse_size
from whoosh.analysis import CharsetFilter
from whoosh.fields import NUMERIC
from whoosh.qparser import FieldAliasPlugin, GtLtPlugin, OperatorsPlugin
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
    """Generate aliases for fields made of snake_case words."""
    bits = field.split("_")
    aliases = []

    # Singular from plural
    if field.endswith("s"):
        aliases += [field[:-1]]

    # Alternate delimiters
    for connector in ("", "-"):
        joined = connector.join(bits)
        aliases += [joined, joined[:-1]]
    return aliases


class FILESIZE(NUMERIC):
    """NUMERIC class with humanized filesize parser."""

    @staticmethod
    def _parse_size(value):
        """Parse the value for size suffixes."""
        try:
            value = str(parse_size(value))
        except InvalidSize as exc:
            LOG.debug(exc)
        return value

    def parse_query(self, fieldname, qstring, boost=1.0):
        """Parse one term."""
        qstring = self._parse_size(qstring)
        return super().parse_query(fieldname, qstring, boost=boost)

    def parse_range(self, fieldname, start, end, startexcl, endexcl, boost=1.0):
        """Parse range terms."""
        if start:
            start = self._parse_size(start)
        if end:
            end = self._parse_size(end)
        return super().parse_range(
            fieldname, start, end, startexcl, endexcl, boost=boost
        )


class CodexSearchBackend(WhooshSearchBackend):
    """Custom Whoosh Backend."""

    FIELDMAP = {
        "characters": ["category", "character"],
        "created_at": ["created"],
        "creators": ["author", "authors", "contributor", "contributors", "creator"],
        "community_rating": gen_multipart_field_aliases("community_rating"),
        "critical_rating": gen_multipart_field_aliases("critical_rating"),
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
    FIELD_ALIAS_PLUGIN = FieldAliasPlugin(FIELDMAP)
    OPERATORS_PLUGIN = OperatorsPlugin(
        ops=None,
        clean=False,
        And=r"(?i)(?<=\s)AND(?=\s)",
        Or=r"(?i)(?<=\s)OR(?=\s)",
        AndNot=r"(?i)(?<=\s)ANDNOT(?=\s)",
        AndMaybe=r"(?i)(?<=\s)ANDMAYBE(?=\s)",
        Not=r"(?i)(^|(?<=(\s|[()])))NOT(?=\s)",
        Require=r"(?i)(^|(?<=\s))REQUIRE(?=\s)",
    )

    def build_schema(self, fields):
        """Customize schema fields."""
        content_field_name, schema = super().build_schema(fields)

        # Add accent leniency to all text field.
        for _, field in schema.items():
            if isinstance(field, TEXT):
                field.analyzer |= CharsetFilter(accent_map)

        # Replace size field with FILESIZE type.
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
        """Add extra plugins."""
        super().setup()
        self.parser.add_plugins(
            (
                self.FIELD_ALIAS_PLUGIN,
                GtLtPlugin,
                DateParserPlugin(basedate=now()),
                # RegexPlugin,  # not working yet
            )
        )
        self.parser.replace_plugin(self.OPERATORS_PLUGIN)


class CodexSearchQuery(WhooshSearchQuery):
    """Custom search qeuery."""

    def clean(self, query_fragment):
        """Optimize to noop because RESERVED_ consts are null."""
        return query_fragment


class CodexSearchEngine(WhooshEngine):
    """A search engine with a locking backend."""

    backend = CodexSearchBackend
    query = CodexSearchQuery
    unified_index = CodexUnifiedIndex
