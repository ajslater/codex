"""Start and stop daemons."""


def start_daemons():
    """Start the daemons. But don't import them until django is set up."""
    from codex.librarian.librariand import start_librarian
    from codex.websocket_server import start_flood_control_worker

    start_flood_control_worker()
    start_librarian()


def stop_daemons():
    """Stop the daemons. But don't import them until django is set up."""
    from codex.librarian.librariand import stop_librarian
    from codex.websocket_server import stop_flood_control_worker

    stop_flood_control_worker()
    stop_librarian()
