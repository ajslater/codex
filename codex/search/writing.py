"""Custom Codex Writer."""
from threading import RLock
from time import sleep

from whoosh.index import FileIndex, LockError
from whoosh.reading import MultiReader
from whoosh.writing import BufferedWriter


class AbortOperationError(Exception):
    """Interrupt the operation because something more important happened."""


class CodexWriter(BufferedWriter):
    """MP safe Buffered Writer that locks the index writer much more granularly.

    XXX The period and limit args are ignored and this writer behaves more like the
    AsycnWriter. The AsyncWriter could possibly be extended to not lock until commit
    time like this one and use less code.
    """

    # For waiting for the writer lock
    _DELAY = 0.25

    def __init__(self, index, writerargs=None, commitargs=None):
        """Initialize with special values."""
        # Same as BufferedWriter init without caching the index.writer() as self.writer
        self.index = index
        self.writerargs = writerargs or {}
        self.commitargs = commitargs or {}

        self.lock = RLock()

        self._make_ram_index()

        # Caching the schema so it doesn't need to derive from a writer every time.
        self._schema = None
        # Debug dict to print on close to diagnose what's waiting for locks.
        self._time_sleeping = {}

    def get_writer(self, caller="unknown"):
        """Wait for the lock to be available and furnish the writer."""
        writer = None
        while writer is None:
            try:
                writer = self.index.refresh().writer(**self.writerargs)
            except LockError:
                sleep(self._DELAY)
                if caller not in self._time_sleeping:
                    self._time_sleeping[caller] = 0
                self._time_sleeping[caller] += self._DELAY
        return writer

    @property
    def schema(self):
        """Get a cached schema."""
        if not self._schema:
            info = self.index.refresh()._read_toc()  # noqa SLF001
            self._schema = info.schema
        return self._schema

    def _get_non_locking_writer_reader(self):
        """Get self.writer.reader() without locking.

        Copied from SegmentWriter.reader()

        XXX Runs the risk of being slightly out of date if it's actively being
        written by other procs.
        """
        with self.lock:
            ramreader = self._get_ram_reader()

        index = self.index.refresh()
        info = index._read_toc()  # noqa SLF001
        return FileIndex._reader(  # noqa SLF001
            index.storage,
            info.schema,
            info.segments,
            info.generation + 1,
            # using the ram index for reuse massively reduces
            # duplication, but is a hack.
            reuse=ramreader,
        )

    def reader(self, **kwargs):
        """Get the reader without locking the writer."""
        reader = self._get_non_locking_writer_reader()

        with self.lock:
            ramreader = self._get_ram_reader()

        # If there are in-memory docs, combine the readers
        if ramreader.doc_count():
            if reader.is_atomic():
                reader = MultiReader([reader, ramreader])
            else:
                reader.add_reader(ramreader)  # type: ignore

        return reader

    def commit(self, reader=None, **kwargs):
        """Commit with a writer we get now."""
        with self.lock:
            ramreader = self._get_ram_reader()
        self._make_ram_index()

        writer = self.get_writer("commit")
        if reader:
            writer.add_reader(reader)
        writer.add_reader(ramreader)
        writer.commit(**self.commitargs)

    def add_reader(self, reader):
        """Do a commit with the supplied reader."""
        # Pass through to the underlying on-disk index
        self.commit(reader=reader)

    def add_document(self, **fields):
        """Add a document with the cached schema."""
        with self.lock, self.codec.writer(self.schema) as w:
            # Hijack a writer to make the calls into the codec
            w.add_document(**fields)

    def delete_document(self, docnum, delete=True, writer=None):
        """Delete a document by getting the writer."""
        # Also count deletes as bufferedcounts as they're batched
        # and not matched to every add.
        with self.lock:
            base = self.index.refresh().doc_count_all()
            if docnum < base:
                if not writer:
                    writer = self.get_writer("delete_document")
                writer.delete_document(docnum, delete=delete)
            else:
                ramsegment = self.codec.segment
                ramsegment.delete_document(docnum - base, delete=delete)

    def is_deleted(self, docnum):
        """Check if document is deleted with temporary writer."""
        base = self.index.refresh().doc_count_all()
        if docnum < base:
            writer = self.get_writer("is_deleted")
            is_deleted = writer.is_deleted(docnum)
            writer.cancel()
            return is_deleted
        return self._get_ram_reader().is_deleted(docnum - base)

    def delete_by_query(self, q, searcher=None):
        """Delete any documents matching a query object.

        :returns: the number of documents deleted.
        Called by multiprocessing.
        """
        s = searcher if searcher else self.searcher()

        count = 0
        writer = self.get_writer("delete_by_query")  # LOCKS WRITING
        try:
            docnums = s.docs_for_query(q, for_deletion=True)
            for docnum in docnums:
                self.delete_document(docnum, writer=writer)
                count += 1
        finally:
            if not searcher:
                s.close()
            with self.lock:
                try:
                    writer.commit(**self.commitargs)
                except (FileNotFoundError, NameError):
                    # XXX This is a multiprocessing error.
                    # either the toc fragment we're looking for doesn't exist
                    # or the one we're trying to write already exists.
                    writer.cancel()
                    count = 0
                except Exception:
                    writer.cancel()
                    raise

        return count

    def delete_docnums(self, docnums, sc=None, status=None, queue=None):
        """Delete all docunums.

        :returns: the number of documents deleted.
        Single threaded.
        """
        count = 0
        writer = self.get_writer("delete_docnums")
        try:
            for docnum in docnums:
                if queue and not queue.empty():
                    raise AbortOperationError()  # noqa TRY301
                self.delete_document(docnum, writer=writer)
                count += 1
                if sc and status:
                    status.complete = count
                    sc.update(status)
        finally:
            with self.lock:
                writer.commit(**self.commitargs)
        return count
