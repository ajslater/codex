"""The librarian process routes the global loguru logger to codex's sinks."""

from unittest.mock import MagicMock, call, patch

from codex.librarian.librariand import LibrarianDaemon


def test_run_reinstalls_logger_before_logging() -> None:
    """
    ``run`` points the process's global logger at codex's sinks first.

    Under the spawn/forkserver start methods the librarian imports a
    fresh ``loguru.logger`` that writes to stderr in loguru's default
    format. Anything logged before ``reinstall`` skips codex's sinks.
    """
    log = MagicMock()
    daemon = LibrarianDaemon(log, MagicMock(), MagicMock())
    daemon.run_loop = False
    log.reset_mock()
    with (
        patch("codex.librarian.librariand.enable_persistent_connections"),
        patch.object(LibrarianDaemon, "_startup"),
        patch.object(LibrarianDaemon, "_shutdown"),
    ):
        daemon.run()
    assert log.method_calls[0] == call.reinstall()
