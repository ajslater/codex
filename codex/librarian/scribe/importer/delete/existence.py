"""
Confirm a scanner's deletes against the filesystem before acting on them.

Deleting a comic row cascades its bookmarks and read progress away, and
nothing restores them — the next scan re-imports the file as a fresh,
unread comic. So a delete is only safe when the file is really gone.

Both scanners infer deletes rather than observing them, and every inference
they make has failure modes: a watcher batch that reports a delete whose
paired add lands in the *next* batch, a directory expansion that overmatched,
an inode pair the compatibility checks refused. In each case the path is
still on disk, and the delete is wrong.

Probing the path is cheap next to what it protects, and a path that is
genuinely gone answers immediately. A row skipped here is not stranded: it
still points at a real file, so the next scan reconciles it normally — a
stale row costs a re-read, a wrongly deleted one costs the user's place in
the book.

The probe fails closed. Only ``ENOENT`` and ``ENOTDIR`` mean gone (see
:mod:`codex.librarian.fs.gone`); a permission error or a dropped share
leaves the path in the keep pile, because "I could not look" is not
"it is not there". That is the case a bare ``Path.exists()`` used to get
wrong, silently, for a whole directory at a time.

An outage that answers ``ENOENT`` for files that exist defeats all of
that, because "not found" is what a real deletion looks like. The short
shape of it — a share that lies for a few seconds during a reconnect, an
external ``rm`` + ``mv`` caught mid-swap — is covered by
``revived_paths``: the delete phase probes once, waits, and probes the
gone set again, keeping anything that answers the second time.

A *sustained* outage still reads as a real deletion here.
``unmounted_reason`` catches the whole-library shape; a subtree-sized one
needs confirmation across polls, which is why the delete phase logs what
it could not check and how much it is about to remove.
"""

from collections.abc import Callable, Collection
from pathlib import Path

from codex.librarian.fs.gone import GONE_ERRORS

#: Unreadable paths named in the delete phase's warning.
_UNREADABLE_EXAMPLES = 3
#: Seconds between the two probes of a delete set. Long enough for a CIFS
#: reconnect or an ``rm`` + ``mv`` swap to settle, short enough not to
#: stall the single scribe worker. It is spent on
#: ``abort_event.wait``, so an admin abort cuts it short; a daemon
#: shutdown does not set that event, so a shutdown landing inside the
#: wait costs at most one delay. Tests patch the wait, not this.
SECOND_LOOK_DELAY_S = 5


def probe_paths(
    paths: Collection[str],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[str, OSError], ...]]:
    """Partition paths into (gone from disk, still on disk, unreadable)."""
    gone: list[str] = []
    extant: list[str] = []
    unreadable: list[tuple[str, OSError]] = []
    for path in paths:
        try:
            Path(path).stat()
        except GONE_ERRORS:
            gone.append(path)
        except OSError as exc:
            # Unknown, so keep it. A row that survives a permission
            # error costs a re-read; one deleted by it costs bookmarks.
            unreadable.append((path, exc))
            extant.append(path)
        else:
            extant.append(path)
    return tuple(gone), tuple(extant), tuple(unreadable)


def split_extant(paths: Collection[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Partition paths into (gone from disk, still on disk)."""
    gone, extant, _ = probe_paths(paths)
    return gone, extant


def confirm_deleted(paths: Collection[str], log, kind: str) -> tuple[str, ...]:
    """Return only the paths that are really gone, reporting any that aren't."""
    gone, extant, unreadable = probe_paths(paths)
    if extant:
        reason = (
            f"Not deleting {len(extant)} {kind} a scan reported missing that"
            f" are still on disk. The next scan will reconcile them."
        )
        log.warning(reason)
    if unreadable:
        # Name the errors: a recurrence is only diagnosable if the log
        # says which failure mode the filesystem answered with.
        errors = "; ".join(sorted({str(exc) for _path, exc in unreadable}))
        examples = ", ".join(path for path, _exc in unreadable[:_UNREADABLE_EXAMPLES])
        reason = (
            f"{len(unreadable)} {kind} could not be checked, so they are"
            f" not deleted ({errors}): {examples}..."
        )
        log.warning(reason)
    return gone


def revived_paths(
    paths: Collection[str], wait: Callable[[float], object]
) -> frozenset[str]:
    """
    Return paths that answered gone, then answered again moments later.

    One observation cannot tell a deletion from a filesystem having a
    bad second. Two can, for the short shape: probe, wait, and re-probe
    only what came back missing. A path that reappears was never gone,
    and deleting it would have cascaded a comic's bookmarks away for a
    file sitting right there.

    Nothing gone means nothing to re-probe, so a healthy scan never
    waits.
    """
    gone, _extant = split_extant(paths)
    if not gone:
        return frozenset()
    wait(SECOND_LOOK_DELAY_S)
    _gone_again, revived = split_extant(gone)
    return frozenset(revived)
