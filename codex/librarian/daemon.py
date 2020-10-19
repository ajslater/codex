"""Start and stop daemons."""


def start_daemons():
    """Start the daemons. But don't import them until django is set up."""
    from codex.librarian.librariand import LibrarianDaemon
    from codex.websocket_server import FloodControlThread

    LibrarianDaemon.startup()
    FloodControlThread.startup()


def stop_daemons():
    """Stop the daemons. But don't import them until django is set up."""
    from codex.librarian.librariand import LibrarianDaemon
    from codex.websocket_server import FloodControlThread

    LibrarianDaemon.stop()
    FloodControlThread.shutdown()
