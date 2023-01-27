"""Custom Haystack Search Backend."""
from datetime import datetime, timedelta
from multiprocessing import cpu_count

from django.utils.timezone import now
from haystack.backends.whoosh_backend import TEXT, WhooshSearchBackend
from haystack.exceptions import SkipDocument
from haystack.utils import get_identifier
from humanfriendly import InvalidSize, parse_size
from humanize import naturaldelta
from whoosh.analysis import CharsetFilter, StandardAnalyzer, StemFilter
from whoosh.fields import NUMERIC
from whoosh.qparser import FieldAliasPlugin, GtLtPlugin, OperatorsPlugin
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.support.charset import accent_map
from whoosh.writing import AsyncWriter

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.status_control import StatusControl
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


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
    MULTISEGMENT_CUTOFF = 500
    UPDATE_DELTA = timedelta(seconds=5)
    UPDATE_FINISH_TYPES = frozenset(
        (
            SearchIndexStatusTypes.SEARCH_INDEX_PREPARE,
            SearchIndexStatusTypes.SEARCH_INDEX_COMMIT,
        )
    )

    def build_schema(self, fields):
        """Customize schema fields."""
        content_field_name, schema = super().build_schema(fields)

        # Add accent leniency to all text field.
        for _, field in schema.items():
            if isinstance(field, TEXT):
                field.analyzer = (
                    StandardAnalyzer()
                    | CharsetFilter(accent_map)
                    | StemFilter(cachesize=-1)
                )

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

    @classmethod
    def get_writerargs(cls, num_objs):
        """Use multiproc, multisegment writing only for large loads."""
        writerargs = {
            "limitdb": 256,
        }
        if num_objs > cls.MULTISEGMENT_CUTOFF:
            # Bug in Whoosh means procs > 1 needs multisegment
            # https://github.com/mchaput/whoosh/issues/35
            writerargs["procs"] = cpu_count()
            writerargs["multisegment"] = cpu_count() > 1
        return writerargs

    def update(self, index, iterable, commit=True):
        """Update index, but with writer options."""
        try:
            start = since = datetime.now()
            num_objs = len(iterable)
            statuses = {
                SearchIndexStatusTypes.SEARCH_INDEX_PREPARE: {
                    "total": num_objs,
                },
                SearchIndexStatusTypes.SEARCH_INDEX_COMMIT: {"name": f"({num_objs})"},
            }
            StatusControl.start_many(statuses)
            if not self.setup_complete:
                self.setup()

            self.index = self.index.refresh()

            writerargs = self.get_writerargs(num_objs)
            writer = AsyncWriter(self.index, writerargs=writerargs)

            for obj_count, obj in enumerate(iterable):
                try:
                    doc = index.full_prepare(obj)
                except SkipDocument:
                    self.log.debug("Indexing for object `%s` skipped", obj)
                else:
                    # Really make sure it's unicode, because Whoosh won't have it any
                    # other way.
                    for key in doc:
                        doc[key] = self._from_python(doc[key])

                    # Document boosts aren't supported in Whoosh 2.5.0+.
                    if "boost" in doc:
                        del doc["boost"]

                    try:
                        writer.update_document(**doc)
                    except Exception:
                        if not self.silently_fail:
                            raise

                        # We'll log the object identifier but won't include the actual
                        # object to avoid the possibility of that generating encoding
                        # errors while processing the log message:
                        self.log.exception(
                            "Preparing object for update",
                            extra={
                                "data": {"index": index, "object": get_identifier(obj)}
                            },
                        )
                since = StatusControl.update(
                    SearchIndexStatusTypes.SEARCH_INDEX_PREPARE,
                    obj_count,
                    num_objs,
                    since=since,
                )

            StatusControl.finish(SearchIndexStatusTypes.SEARCH_INDEX_PREPARE)
            elapsed = naturaldelta(datetime.now() - start)
            LOG.verbose(f"Search engine prepared objects for commit in {elapsed}")

            start = datetime.now()
            if len(iterable) > 0:
                # For now, commit no matter what, as we run into locking issues
                # otherwise.
                if commit:
                    writer.commit(merge=True)
                if writer.ident is not None:
                    writer.join()
            elapsed = naturaldelta(datetime.now() - start)
            LOG.verbose(f"Search engine committed index in {elapsed}")
        finally:
            StatusControl.finish_many(self.UPDATE_FINISH_TYPES)

    def clear(self, models=None, commit=True):
        """Clear index with codex status messages."""
        try:
            StatusControl.start(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
            super().clear(models=models, commit=commit)
        finally:
            StatusControl.finish(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
