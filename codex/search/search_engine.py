"""Locking, Aliasing Xapian Backend."""
from django.utils.timezone import now
from haystack.backends import UnifiedIndex
from haystack.backends.whoosh_backend import WhooshEngine, WhooshSearchBackend
from whoosh.qparser import FieldAliasPlugin, GtLtPlugin
from whoosh.qparser.dateparse import DateParserPlugin

from codex.search.search_indexes import ComicIndex


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

    def setup(self):
        super().setup()
        self.parser.add_plugins(
            [
                GtLtPlugin,
                FieldAliasPlugin(self.FIELDMAP),
                DateParserPlugin(basedate=now()),
            ]
        )


class CodexSearchEngine(WhooshEngine):
    """A search engine with a locking backend."""

    backend = CodexSearchBackend
    unified_index = CodexUnifiedIndex
