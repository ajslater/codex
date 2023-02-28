"""Search Engine to database matching."""
from uuid import uuid4

from codex.librarian.search.tasks import SearchIndexUpdateTask
from codex.models import Timestamp
from codex.search.engine import CodexSearchEngine
from codex.settings.settings import SEARCH_INDEX_PATH, SEARCH_INDEX_UUID_PATH
from codex.threads import QueuedThread


class VersionMixin(QueuedThread):
    """Search Engine to database matching methods."""

    def __init__(self, *args, **kwargs):
        """Initialize search engine."""
        super().__init__(*args, **kwargs)
        queue_kwargs = {
            "log_queue": self.log_queue,
            "librarian_queue": self.librarian_queue,
        }
        self.engine = CodexSearchEngine(queue_kwargs=queue_kwargs)

    def _set_search_index_version(self):
        """Set the codex db to search index matching id."""
        version = str(uuid4())
        try:
            lv = Timestamp.objects.get(name=Timestamp.SEARCH_INDEX_UUID)
            lv.version = version
            lv.save()
            SEARCH_INDEX_PATH.mkdir(parents=True, exist_ok=True)
            with SEARCH_INDEX_UUID_PATH.open("w") as uuid_file:
                uuid_file.write(version)
        except Exception as exc:
            self.log.error(f"Setting search index to db synchronization token: {exc}")

    def _is_search_index_uuid_match(self):
        """Is this search index for this database."""
        result = False
        try:
            with SEARCH_INDEX_UUID_PATH.open("r") as uuid_file:
                version = uuid_file.read()
            result = Timestamp.objects.filter(
                name=Timestamp.SEARCH_INDEX_UUID, version=version
            ).exists()
        except (FileNotFoundError, Timestamp.DoesNotExist):
            pass
        except Exception as exc:
            self.log.exception(exc)
        return result

    def _rebuild_search_index_if_db_changed(self):
        """Rebuild the search index if the db changed."""
        if not self._is_search_index_uuid_match():
            self.log.warning("Database does not match search index.")
            task = SearchIndexUpdateTask(True)
            self.librarian_queue.put(task)
        else:
            self.log.info("Database matches search index.")
