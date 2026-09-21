"""Per-run temporary directories for test fixtures."""

import atexit
import shutil
import tempfile
from os import getpid
from pathlib import Path
from typing import Final

# Every fixture directory in the suite hangs off this root. ``mkdtemp``
# creates it atomically with a random suffix, so two suites running at the
# same time — most often the same repo checked out into two git worktrees —
# never share a path. Before this, modules hardcoded ``/tmp/<name>``, and one
# run's ``tearDownClass`` ``rmtree``'d the *other* run's library mid-test. The
# fixture comic vanished, the import silently produced zero rows, and
# assertions like ``credit_primary_count == 2`` saw ``0``. The failures moved
# around from run to run and every one of them passed in isolation.
#
# The pid rides in the prefix so a leftover directory names the process that
# abandoned it. ``/tmp`` stays the base rather than ``tempfile.gettempdir()``
# so fixture libraries land in the same predictable place on a developer's
# machine as in CI, where ``TMPDIR`` is unset.
_RUN_ROOT: Final = Path(tempfile.mkdtemp(prefix=f"codex.tests.{getpid()}.", dir="/tmp"))


@atexit.register
def _rmtree_run_root() -> None:
    """Remove the run's fixture root so ``/tmp`` does not accumulate."""
    shutil.rmtree(_RUN_ROOT, ignore_errors=True)


def tmp_dir(name: str) -> Path:
    """
    Return this run's private fixture directory named ``name``.

    The directory itself is *not* created: callers ``mkdir`` it in setup and
    ``rmtree`` it in teardown exactly as they did when the path was
    hardcoded. Only the parent is guaranteed to exist, which is what lets a
    bare ``mkdir(exist_ok=True)`` keep working.
    """
    return _RUN_ROOT / name
