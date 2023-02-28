"""Custom Haystack Search Backend."""
from logging import getLogger
from multiprocessing import cpu_count
from queue import SimpleQueue
from sys import maxsize
from time import time

from django.utils.timezone import now
from haystack.backends.whoosh_backend import TEXT, WhooshSearchBackend
from haystack.exceptions import SkipDocument
from humanfriendly import InvalidSize, parse_size
from humanize import naturaldelta
from whoosh.analysis import CharsetFilter, StandardAnalyzer, StemFilter
from whoosh.fields import NUMERIC
from whoosh.qparser import FieldAliasPlugin, GtLtPlugin, OperatorsPlugin
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.support.charset import accent_map
from whoosh.writing import MERGE_SMALL, BufferedWriter

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.logger.logging import get_logger
from codex.status_controller import StatusController
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

    @staticmethod
    def _parse_size(value):
        """Parse the value for size suffixes."""
        try:
            value = str(parse_size(value))
        except InvalidSize as exc:
            FILESIZE.LOG.debug(exc)
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


class CodexSearchBackend(WhooshSearchBackend, WorkerBaseMixin):
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
    STATUS_FINISH_TYPES = frozenset(
        (
            SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
            SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
        )
    )
    WRITERARGS = {
        "limitmb": maxsize,
        "procs": cpu_count(),
        # Bug in Whoosh means procs > 1 needs multisegment
        # https://github.com/mchaput/whoosh/issues/35
        "multisegement": True,
    }
    COMMITARGS = {"merge": True, "mergetype": MERGE_SMALL}

    def __init__(self, connection_alias, **connection_options):
        """Init worker queues."""
        log_queue = connection_options.pop("log_queue", None)
        librarian_queue = connection_options.pop("librarian_queue", None)
        if log_queue and librarian_queue:
            self.init_worker(log_queue, librarian_queue)
        else:
            self.log = getLogger(self.__class__.__name__)
            self.log.propagate = False
            self.status_controller = StatusController(SimpleQueue(), SimpleQueue())
        super().__init__(connection_alias, **connection_options)

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

    def update(self, index, iterable, commit=True):
        """Update index, but with writer options."""
        start = since = time()
        try:
            num_objs = len(iterable)
            if num_objs < 1:
                self.log.debug("Search index nothing to update.")
                return

            statuses = {
                SearchIndexStatusTypes.SEARCH_INDEX_UPDATE: {
                    "total": num_objs,
                },
                # SearchIndexStatusTypes.SEARCH_INDEX_COMMIT: {},
            }
            self.status_controller.start_many(statuses)
            if not self.setup_complete:
                self.setup()

            self.index = self.index.refresh()

            # writer = AsyncWriter(self.index, writerargs=self.WRITERARGS)
            writer = BufferedWriter(
                self.index,
                limit=maxsize,
                period=60 * 5,
                writerargs=self.WRITERARGS,
                commitargs=self.COMMITARGS,
            )

            obj_count = 0
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
                    except Exception as exc:
                        if not self.silently_fail:
                            raise

                        # We'll log the object identifier but won't include the actual
                        # object to avoid the possibility of that generating encoding
                        # errors while processing the log message:
                        self.log.warning(
                            f"Search index updating document {exc} pk:{obj.pk}",
                        )
                since = self.status_controller.update(
                    SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
                    obj_count,
                    num_objs,
                    since=since,
                )
            prepare_start = time()
            try:
                if obj_count > 1:
                    self.log.debug("Search index beginning final commit.")
                    writer.commit()
                else:
                    self.log.debug("Search index update cancelling nothing to update.")
                    writer.cancel()
            except Exception as exc:
                self.log.error("During search index writer final commit or cancel.")
                self.log.exception(exc)

            writer.close()

            elapsed_time = time() - start
            elapsed = naturaldelta(elapsed_time)
            cps = int(num_objs / elapsed_time)
            self.log.info(
                f"Search engine updated {num_objs} comics"
                f" in {elapsed} at {cps} comics per second."
            )
            until = prepare_start + 1
            self.status_controller.finish(
                SearchIndexStatusTypes.SEARCH_INDEX_UPDATE, until=until
            )

        finally:
            until = start + 1
            self.status_controller.finish_many(self.STATUS_FINISH_TYPES, until=until)

    def clear(self, models=None, commit=True):
        """Clear index with codex status messages."""
        start = time()
        try:
            self.status_controller.start(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
            super().clear(models=models, commit=commit)
        finally:
            until = start + 1
            self.status_controller.finish(
                SearchIndexStatusTypes.SEARCH_INDEX_CLEAR, until=until
            )

    def remove_batch(self, doc_ids):
        """Remove a large batch of doc ids from the index."""
        num_doc_ids = len(doc_ids)
        self.status_controller.start(
            SearchIndexStatusTypes.SEARCH_INDEX_REMOVE, num_doc_ids
        )
        start = since = time()
        try:
            if not self.setup_complete:
                self.setup()

            self.index = self.index.refresh()
            writer = BufferedWriter(
                self.index,
                limit=maxsize,
                period=60 * 5,
                writerargs=self.WRITERARGS,
                commitargs=self.COMMITARGS,
            )
            count = 0
            for count, doc_id in enumerate(doc_ids):
                writer.delete_document(doc_id)
                since = self.status_controller.update(
                    SearchIndexStatusTypes.SEARCH_INDEX_REMOVE,
                    count,
                    num_doc_ids,
                    since=since,
                )

            if len(doc_ids) > 1:
                writer.commit()
            else:
                writer.cancel()
            writer.close()

            elapsed_time = time() - start

            elapsed = naturaldelta(elapsed_time)
            cps = int(count / elapsed_time)
            self.log.info(
                f"Search engine removed {count} ghosts from the index"
                f" in {elapsed} at {cps} per second."
            )
        finally:
            until = start + 1
            self.status_controller.finish(
                SearchIndexStatusTypes.SEARCH_INDEX_REMOVE, until=until
            )

    def optimize(self):
        """Optimize the index."""
        if not self.setup_complete:
            self.setup()
        self.index = self.index.refresh()
        self.index.optimize(**self.WRITERARGS)
