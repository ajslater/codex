"""Custom Codex Writer."""
from threading import RLock, Timer
from time import sleep, time

from whoosh.index import FileIndex, LockError
from whoosh.writing import BufferedWriter

from codex.librarian.search.status import SearchIndexStatusTypes


class CodexWriter(BufferedWriter):
    """MP safe Buffered Writer that locks the index writer much more granularly."""

    def __init__(self, index, period=60, limit=10, writerargs=None, commitargs=None):
        """Initialize with special values."""
        self.index = index
        self.period = period
        self.limit = limit
        self.writerargs = writerargs or {}
        self.commitargs = commitargs or {}

        self.lock = RLock()
        # self.writer = None #self.index.writer(**self.writerargs)

        self._make_ram_index()
        self.bufferedcount = 0

        # Start timer
        if self.period:
            self.timer = Timer(self.period, self.commit)
            self.timer.start()

        self.delay = 0.25
        self._schema = None
        self._time_sleeping = {}

    def get_writer(self, caller="unknown"):
        """Wait for the lock to be available and furnish the writer."""
        writer = None
        while writer is None:
            try:
                writer = self.index.writer(**self.writerargs)
            except LockError:
                sleep(self.delay)
                if caller not in self._time_sleeping:
                    self._time_sleeping[caller] = 0
                self._time_sleeping[caller] += self.delay
        return writer

    @property
    def schema(self):
        """Get a cached schema."""
        if not self._schema:
            self._schema = self.index._read_toc().schema
        return self._schema

    def reader(self, **kwargs):
        """Get the reader without locking the writer."""
        from whoosh.reading import MultiReader

        with self.lock:
            ramreader = self._get_ram_reader()

        info = self.index._read_toc()
        generation = info.generation + 1
        # using the ram index for reuse massively reduces duplication, but is a hack.
        reader = FileIndex._reader(
            self.index.storage, info.schema, info.segments, generation, reuse=ramreader
        )

        # Reopen the ram index
        with self.lock:
            ramreader = self._get_ram_reader()

        # If there are in-memory docs, combine the readers
        if ramreader.doc_count():
            if reader.is_atomic():
                reader = MultiReader([reader, ramreader])
            else:
                reader.add_reader(ramreader)  # type: ignore

        return reader

    def commit(self, restart=True, reader=None):
        """Commit with a writer we get now."""
        if self.period:
            self.timer.cancel()

        with self.lock:
            ramreader = self._get_ram_reader()
            self._make_ram_index()

        writer = self.get_writer("commit")
        if reader:
            writer.add_reader(reader)
        if self.bufferedcount:
            writer.add_reader(ramreader)
        writer.commit(**self.commitargs)
        self.bufferedcount = 0

        if restart:
            if self.period:
                self.timer = Timer(self.period, self.commit)
                self.timer.start()

    def add_reader(self, reader):
        """Do a commit with the supplied reader."""
        # Pass through to the underlying on-disk index
        self.commit(reader=reader)

    def add_document(self, **fields):
        """Add a document with the cached schema."""
        with self.lock:
            # Hijack a writer to make the calls into the codec
            with self.codec.writer(self.schema) as w:
                w.add_document(**fields)

            self.bufferedcount += 1
            if self.bufferedcount >= self.limit:
                self.commit()

    def delete_document(self, docnum, delete=True, writer=None, commit=True):
        """Delete a document by getting the writer."""
        with self.lock:
            base = self.index.doc_count_all()
            if docnum < base:
                if not writer:
                    writer = self.get_writer("delete_document")
                writer.delete_document(docnum, delete=delete)
                if commit:
                    writer.commit(**self.commitargs)
            else:
                ramsegment = self.codec.segment
                ramsegment.delete_document(docnum - base, delete=delete)

    def is_deleted(self, docnum):
        """Check if document is deleted with temporary writer."""
        base = self.index.doc_count_all()
        if docnum < base:
            writer = self.get_writer("is_deleted")
            is_deleted = writer.is_deleted(docnum)
            writer.cancel()
            return is_deleted
        else:
            return self._get_ram_reader().is_deleted(docnum - base)

    def delete_by_query(self, q, searcher=None, sc=None):
        """Delete any documents matching a query object.

        :returns: the number of documents deleted.

        Special codex version with progress updates.
        """
        if searcher:
            s = searcher
        else:
            s = self.searcher()

        try:
            count = 0
            docnums = s.docs_for_query(q, for_deletion=True)
            if sc:
                since = time()
                sc.start(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)
            for docnum in docnums:
                self.delete_document(docnum)
                count += 1
                if sc:
                    since = sc.update(
                        SearchIndexStatusTypes.SEARCH_INDEX_REMOVE,
                        complete=count,
                        total=0,
                        since=since,  # type: ignore
                    )
        finally:
            if not searcher:
                s.close()

        return count
