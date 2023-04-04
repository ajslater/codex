"""Custom Haystack Search Backend."""
from math import ceil
from multiprocessing import cpu_count
from pathlib import Path

from django.utils.timezone import now
from haystack.backends.whoosh_backend import (
    WHOOSH_ID,
    WhooshSearchBackend,
)
from haystack.constants import DJANGO_CT, DJANGO_ID, ID
from haystack.exceptions import SearchBackendError, SkipDocument
from humanfriendly import InvalidSize, parse_size
from whoosh.analysis import CharsetFilter, StandardAnalyzer, StemFilter
from whoosh.fields import BOOLEAN, DATETIME, NUMERIC, TEXT, FieldType, Schema
from whoosh.filedb.filestore import FileStorage
from whoosh.index import EmptyIndexError
from whoosh.qparser import (
    FieldAliasPlugin,
    GtLtPlugin,
    OperatorsPlugin,
    WhitespacePlugin,
)
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.query import Or, Term
from whoosh.support.charset import accent_map

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.logger.logging import get_logger
from codex.memory import get_mem_limit
from codex.models import Comic
from codex.search.indexes import ComicIndex
from codex.search.writing import CodexWriter
from codex.settings.settings import (
    CHUNK_PER_GB,
    CPU_MULTIPLIER,
    MAX_CHUNK_SIZE,
    MMAP_RATIO,
    WRITER_MEMORY_PERCENT,
)
from codex.worker_base import WorkerBaseMixin


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

    LOG = get_logger("FILESIZE")

    @classmethod
    def _parse_size(cls, value):
        """Parse the value for size suffixes."""
        try:
            value = str(parse_size(value))
        except InvalidSize as exc:
            cls.LOG.debug(exc)
        return value

    def parse_query(self, fieldname, qstring, boost=1.0):
        """Parse one term."""
        qstring = self._parse_size(qstring)
        return super().parse_query(fieldname, qstring, boost=boost)

    def parse_range(  # noqa PLR0913
        self, fieldname, start, end, startexcl, endexcl, boost=1.0
    ):
        """Parse range terms."""
        if start:
            start = self._parse_size(start)
        if end:
            end = self._parse_size(end)
        return super().parse_range(
            fieldname, start, end, startexcl, endexcl, boost=boost
        )


TEXT_ANALYZER = (
    StandardAnalyzer() | CharsetFilter(accent_map) | StemFilter(cachesize=-1)
)


class CodexSearchBackend(WhooshSearchBackend, WorkerBaseMixin):
    """Custom Whoosh Backend."""

    FIELDMAP = {
        "characters": ["category", "character"],
        "created_at": ["created"],
        "creators": [
            "author",
            "authors",
            "contributor",
            "contributors",
            "creator",
            "creator",
            "creators",
        ],
        "community_rating": gen_multipart_field_aliases("community_rating"),
        "critical_rating": gen_multipart_field_aliases("critical_rating"),
        "genres": ["genre"],
        "file_type": ["type"],
        "locations": ["location"],
        "name": ["title"],
        "original_format": ["format"],
        "page_count": ["pages"],
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
    STATUS_FINISH_TYPES = frozenset(
        (
            SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
            SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
        )
    )
    WRITER_PERIOD = 0  # No period timer.
    WRITER_LIMIT = 1000
    COMMITARGS_MERGE_SMALL = {"merge": True}
    COMMITARGS_NO_MERGE = {"merge": False}
    _SELECT_RELATED_FIELDS = ("publisher", "imprint", "series", "volume")
    _PREFETCH_RELATED_FIELDS = (
        "characters",
        "creators",
        "genres",
        "locations",
        "series_groups",
        "story_arcs",
        "tags",
        "teams",
        "creators__person",
    )
    _DEFERRED_FIELDS = (
        "parent_folder",
        "library",
        "path",
        "stat",
        # "folders", # don't explicitly defer m2m
        "max_page",
    )
    _ONEMB = 1024**2
    ###################
    # MEMORY CONTROLS #
    ###################
    # Magic number determined by tests
    # The perfect number may be larger than this but is below 369
    _MMAP_RATIO = MMAP_RATIO
    _WRITER_MEMORY_PERCENT = WRITER_MEMORY_PERCENT
    _CPU_MULTIPLIER = CPU_MULTIPLIER
    _CHUNK_PER_GB = CHUNK_PER_GB
    _MAX_CHUNK_SIZE = MAX_CHUNK_SIZE

    def __init__(self, connection_alias, **connection_options):
        """Init worker queues."""
        super().__init__(connection_alias, **connection_options)
        # XXX will only connect to the log listener on Linux with fork
        self.log = get_logger(self.__class__.__name__)
        self.log.propagate = False
        self._set_writerargs()

    def _set_writerargs(self):
        """Get writerargs for this machine's cpu & memory config."""
        mem_limit_mb = get_mem_limit("m")
        mem_limit_gb = mem_limit_mb / 1024
        cpu_max = ceil(mem_limit_gb * self._CPU_MULTIPLIER)
        procs = min(cpu_count(), cpu_max)
        limitmb = mem_limit_mb * self._WRITER_MEMORY_PERCENT / procs
        limitmb = int(limitmb)
        self.writerargs = {"limitmb": limitmb, "procs": procs, "multisegment": True}
        self.chunk_size = min(
            int(mem_limit_gb * self._CHUNK_PER_GB), self._MAX_CHUNK_SIZE
        )

    @staticmethod
    def _get_text_analyzer():
        return StandardAnalyzer() | CharsetFilter(accent_map) | StemFilter(cachesize=-1)

    def build_schema(self, fields):
        """Customize Codex Schema.

        custom size field,
        64 bit unsigned ints.
        16 bit unsigned flaots.
        unsortable text and datetime fields.
        """
        schema_fields: dict[str, FieldType] = {
            ID: WHOOSH_ID(stored=True, unique=True),
            DJANGO_CT: WHOOSH_ID(stored=True),
            DJANGO_ID: WHOOSH_ID(stored=True),
        }

        initial_key_count = len(schema_fields)
        content_field_name = ""

        for field_class in fields.values():
            index_fieldname = field_class.index_fieldname
            if field_class.field_type == "integer":
                schema_field_class = FILESIZE if index_fieldname == "size" else NUMERIC
                schema_fields[index_fieldname] = schema_field_class(
                    numtype=int,
                    bits=64,
                    field_boost=field_class.boost,
                    signed=False,
                    stored=field_class.stored,
                )
            elif field_class.field_type == "float":
                # my only floats are small decimals.
                schema_fields[index_fieldname] = NUMERIC(
                    numtype=int,  # Decimal is converted to int in NUMERIC
                    bits=64,
                    field_boost=field_class.boost,
                    signed=False,
                    decimal_places=2,
                    stored=field_class.stored,
                )
            elif field_class.field_type in ["date", "datetime"]:
                schema_fields[index_fieldname] = DATETIME(
                    stored=field_class.stored,
                    # sortable=True  # index_fieldname == "updated_at"
                )
            elif field_class.field_type == "boolean":
                # Field boost isn't supported on BOOLEAN as of 1.8.2.
                schema_fields[index_fieldname] = BOOLEAN(stored=field_class.stored)
            else:
                schema_fields[index_fieldname] = TEXT(
                    stored=True,
                    analyzer=TEXT_ANALYZER,
                    # analyzer=field_class.analyzer  or StemmingAnalyzer(),
                    field_boost=field_class.boost,
                    # sortable=True,
                    spelling=field_class.document is True,
                )
                if field_class.document:
                    content_field_name = index_fieldname

        # Fail more gracefully than relying on the backend to die if no fields
        # are found.
        if len(schema_fields) <= initial_key_count:
            reason = (
                "No fields were found in any search_indexes."
                " Please correct this before attempting to search."
            )
            raise SearchBackendError(reason)

        return (content_field_name, Schema(**schema_fields))

    def _setup_storage_patch(self):
        """Adapt FileStorage to not use mmap in low memory environements."""
        if not self.use_file_storage:
            return

        # Get sizes
        total_size = 0
        if self.path:
            for path in Path(self.path).glob("*.seg"):
                total_size += path.stat().st_size
        total_size_mb = total_size / self._ONEMB
        mem_limit_gb = get_mem_limit("g")

        # Decide
        ratio = total_size_mb / mem_limit_gb
        use_mmap = ratio < self._MMAP_RATIO

        if use_mmap:
            # Don't replace storage and index.
            return

        # Replace storage and index disabling mmap
        self.storage = FileStorage(self.path, supports_mmap=use_mmap)
        try:
            self.index = self.storage.open_index(schema=self.schema)
        except EmptyIndexError:
            self.index = self.storage.create_index(self.schema)
        self.log.debug("Memory limited. Disabled search index mmap")

    def _setup_parser_plugin_patch(self):
        """Set up codex plugins."""
        # Fix duplicate plugin bug:
        # https://github.com/mchaput/whoosh/pull/11
        self.parser.remove_plugin_class(WhitespacePlugin)
        self.parser.replace_plugin(self.OPERATORS_PLUGIN)
        plugins = [WhitespacePlugin, self.FIELD_ALIAS_PLUGIN, GtLtPlugin]
        plugins += [DateParserPlugin(basedate=now())]
        self.parser.add_plugins(plugins)

    def setup(self, patch_plugins=True):
        """Add extra plugins."""
        super().setup()
        self._setup_storage_patch()
        if patch_plugins:
            # The dateparser plugin won't pickle for
            # multiprocessing
            self._setup_parser_plugin_patch()

    def get_writer(self, commitargs=COMMITARGS_NO_MERGE):
        """Get a writer."""
        return CodexWriter(
            self.index.refresh(),
            writerargs=self.writerargs,
            commitargs=commitargs,
        )

    def _update_obj(self, index, writer, batch_num, obj):
        """Update one object."""
        try:
            doc = index.full_prepare(obj)
            # Really make sure it's unicode, because Whoosh won't have it any
            # other way.
            for key in doc:
                doc[key] = self._from_python(doc[key])
        except SkipDocument:
            self.log.debug(f"Indexing for object {obj} skipped in batch {batch_num}")
        except Exception as exc:
            self.log.warning(
                f"Preparing object for indexing: {exc}"
                f" in batch {batch_num}: {obj.path}"
            )
            raise
        else:
            # Document boosts aren't supported in Whoosh 2.5.0+.
            if "boost" in doc:
                del doc["boost"]

            try:
                # add instead of update because of above batch remove
                writer.add_document(**doc)
            except Exception as exc:
                if not self.silently_fail:
                    raise

                # We'll log the object identifier but won't include the actual
                # object to avoid the possibility of that generating encoding
                # errors while processing the log message:
                self.log.warning(
                    f"Search index adding document {exc}"
                    f" in batch {batch_num}: {obj.path}",
                )
                raise
            else:
                return 1
        return 0

    def _update_init(self, index, batch_pks):
        if not self.setup_complete:
            self.setup(False)

        if not index:
            index = ComicIndex()

        writer = self.get_writer()

        try:
            self.remove_django_ids(batch_pks, writer=writer)
        except Exception as exc:
            self.log.warning(
                f"Couldn't delete search index records before replacing: {exc}"
            )
            writer.cancel()
            writer = self.get_writer()

        # prefetch is not pickleable, create the query here from pks.
        iterable = (
            Comic.objects.filter(pk__in=batch_pks)
            .defer(*self._DEFERRED_FIELDS)
            .select_related(*self._SELECT_RELATED_FIELDS)
            .prefetch_related(*self._PREFETCH_RELATED_FIELDS)
            .iterator(chunk_size=self.chunk_size)
        )
        return index, writer, iterable

    def _update_finish(self, count, batch_num, writer):
        """Finish the update by committing or canceling."""
        try:
            if count:
                msg = f"Search index starting final commit for batch {batch_num}."
            else:
                msg = (
                    "Search index update cancelling batch"
                    f" {batch_num} nothing to update."
                )
                writer.cancel()
            self.log.debug(msg)

            writer.close()
        except Exception as exc:
            self.log.debug(f"Writing batch {batch_num} failed: {exc}")
            writer.cancel()
            raise
        return count

    def update(self, index, batch_pks, batch_num=0, abort_event=None, **kwargs):
        """Update index, but with writer options."""
        count = 0
        if abort_event and abort_event.is_set():
            self.log.debug(
                f"Stopped search index update batch {batch_num} before it started."
            )
            return count
        num_objs = len(batch_pks)
        if not num_objs:
            self.log.debug("Search index nothing to update.")
            return count

        index, writer, iterable = self._update_init(index, batch_pks)

        if abort_event and abort_event.is_set():
            self.log.debug(
                f"Stopped search index update batch {batch_num}"
                " after removing old records."
            )
            return count

        for obj in iterable:
            if abort_event and abort_event.is_set():
                self.log.debug(
                    f"Stopped search index update batch {batch_num} at {count} updates."
                )
                break
            count += self._update_obj(index, writer, batch_num, obj)
        return self._update_finish(count, batch_num, writer)

    def remove_django_ids(self, pks, writer, searcher=None):
        """Remove a large batch of docs by pk from the index."""
        # Does not benefit from multiprocessing.
        if not len(pks):
            return 0
        query = Or([Term(DJANGO_ID, str(pk)) for pk in pks])
        return writer.delete_by_query(query, searcher=searcher)

    def remove_docnums(self, docnums):
        """Remove a batch of docnums from the index.."""
        writer = self.get_writer()
        count = 0
        try:
            count = writer.delete_batch_documents(docnums)
        except Exception as exc:
            self.log.warning(f"Search index removing documents by docnums {exc}")
            writer.cancel()
        finally:
            writer.close()
        return count

    def optimize(self):
        """Optimize the index."""
        if not self.setup_complete:
            self.setup(False)
        self.index.refresh().optimize(**self.writerargs)

    def merge_small(self):
        """Merge small segments of the index."""
        if not self.setup_complete:
            self.setup(False)
        writer = self.get_writer({"merge": True})
        writer.close()
