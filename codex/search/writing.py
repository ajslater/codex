"""Custom Codex Writer."""
from threading import RLock
from time import sleep, time

from whoosh.index import FileIndex, LockError
from whoosh.writing import BufferedWriter

from codex.librarian.search.status import SearchIndexStatusTypes


class CodexWriter(BufferedWriter):
    """MP safe Buffered Writer that locks the index writer much more granularly.

    XXX The Codex backend currently sets the period and limit args to where
    they're ignored and this writer behaves more like the AsycnWriter. The
    AsyncWriter could possibly be extended to not lock until commit time like this one
    and use less code.
    """

    # For waiting for the writer lock
    _DELAY = 0.25

    def __init__(self, index, period=0, limit=10, writerargs=None, commitargs=None):
        """Initialize with special values."""
        # Same as BufferedWriter init without caching the index.writer() as self.writer
        self.index = index
        self.period = period
        self.limit = limit
        self.writerargs = writerargs or {}
        self.commitargs = commitargs or {}

        self.lock = RLock()

        self._make_ram_index()
        # self.bufferedcount = 0

        # Start timer
        # if self.period:
        #    self.timer = Timer(self.period, self.commit)
        #    self.timer.start()

        #######################
        # Codex specific init #
        #######################
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
            self._schema = self.index.refresh()._read_toc().schema
        return self._schema

    def reader(self, **kwargs):
        """Get the reader without locking the writer.

        XXX Runs the risk of being slightly out of date if it's actively being
        written by other procs.
        """
        from whoosh.reading import MultiReader

        with self.lock:
            ramreader = self._get_ram_reader()

        info = self.index.refresh()._read_toc()
        generation = info.generation + 1
        # using the ram index for reuse massively reduces duplication, but is a hack.
        reader = FileIndex._reader(
            self.index.refresh().storage,
            info.schema,
            info.segments,
            generation,
            reuse=ramreader,
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
        # if self.period:
        #    self.timer.cancel()

        # with self.lock:
        #    ramreader = self._get_ram_reader()
        #    self._make_ram_index()

        writer = self.get_writer("commit")
        if reader:
            writer.add_reader(reader)
        # if self.bufferedcount:
        #    writer.add_reader(ramreader)
        writer.commit(**self.commitargs)
        # self.bufferedcount = 0

        # if restart and self.period:
        #    self.timer = Timer(self.period, self.commit)
        #    self.timer.start()

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

            # self.bufferedcount += 1
            # if self.bufferedcount >= self.limit:
            #    self.commit()

    def delete_document(self, docnum, delete=True, writer=None):
        """Delete a document by getting the writer."""
        # Also count deletes as bufferedcounts as they're batched
        # and not matched to every add.
        with self.lock:
            base = self.index.refresh().doc_count_all()
            if docnum < base:
                # commit = writer is None
                if not writer:
                    writer = self.get_writer("delete_document")
                writer.delete_document(docnum, delete=delete)
                # self.bufferedcount += 1
                # if self.bufferedcount >= self.limit:
                #    writer.commit(**self.commitargs)
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
        else:
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
                except Exception as exc:
                    writer.cancel()
                    raise exc

        return count

    def delete_docnums(self, docnums, sc=None):
        """Delete all docunums.

        :returns: the number of documents deleted.
        Single threaded.
        """
        count = 0
        num_docnums = len(docnums)
        since = time()
        writer = self.get_writer("delete_docnums")
        for docnum in docnums:
            self.delete_document(docnum, writer=writer)
            count += 1
            if sc:
                since = sc.update(
                    SearchIndexStatusTypes.SEARCH_INDEX_REMOVE,
                    count,
                    num_docnums,
                    since=since,
                )
        with self.lock:
            writer.commit(**self.commitargs)
        return count
