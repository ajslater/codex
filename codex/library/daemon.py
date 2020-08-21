"""Start daemons."""
from codex.library.crond import start_scan_cron
from codex.library.librariand import start_librarian
from codex.library.watcherd import RootPathWatcher


def start_daemons():
    """Start the daemons."""
    start_librarian()
    RootPathWatcher.start_all()
    start_scan_cron()
