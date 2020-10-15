"""Start and stop daemons."""


def start_daemons():
    """Start the daemons. But don't import them until django is set up."""
    from codex.librarian.librariand import LibrarianDaemon
    from codex.websocket_server import start_flood_control_worker

    LibrarianDaemon.start()
    start_flood_control_worker()


def stop_daemons():
    """Stop the daemons. But don't import them until django is set up."""
    from codex.librarian.librariand import LibrarianDaemon
    from codex.websocket_server import stop_flood_control_worker

    LibrarianDaemon.stop()
    stop_flood_control_worker()
