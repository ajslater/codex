"""Search Index cleanup."""
from time import time
from typing import Optional

from humanize import naturaldelta

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.version import VersionMixin
from codex.models import Comic
from codex.search.backend import CodexSearchBackend


class RemoveMixin(VersionMixin):
    """Search Index cleanup methods."""

    def _remove_stale_records(
        self, backend: Optional[CodexSearchBackend] = None  # type: ignore
    ):
        """Remove records not in the database from the index."""
        try:
            start_time = time()
            self.status_controller.start(
                SearchIndexStatusTypes.SEARCH_INDEX_REMOVE, total=0
            )
            if not backend:
                backend: CodexSearchBackend = self.engine.get_backend()  # type: ignore
            if not backend.setup_complete:
                backend.setup(False)

            database_pks = (
                Comic.objects.all().order_by("pk").values_list("pk", flat=True)
            )
            count = backend.remove_batch_pks(
                database_pks, inverse=True, sc=self.status_controller
            )

            if count:
                elapsed_time = time() - start_time
                elapsed = naturaldelta(elapsed_time)
                cps = int(count / elapsed_time)
                self.log.info(
                    f"Removed {count} ghosts from the search index"
                    f" in {elapsed} at {cps} per second."
                )
            else:
                self.log.debug("No ghosts to remove the search index.")
        except Exception as exc:
            self.log.error("While removing stale records:")
            self.log.exception(exc)
        finally:
            self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)
