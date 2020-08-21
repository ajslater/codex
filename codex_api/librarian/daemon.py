"""Start and stop daemons."""


def start_daemons():
    """Start the daemons. But don't import them until django is set up."""
    from codex_api.librarian.librariand import start_librarian
    from codex_api.websocket import start_flood_control_worker

    start_librarian()
    start_flood_control_worker()


def stop_daemons():
    """Stop the daemons. But don't import them until django is set up."""
    from codex_api.librarian.librariand import stop_librarian
    from codex_api.websocket import stop_flood_control_worker

    stop_librarian()
    stop_flood_control_worker()
