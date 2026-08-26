"""
Recognize a library root that isn't really there.

A dropped network share, an ejected volume, or a docker bind mount that
didn't come up presents as an empty (or missing) directory rather than an
error. Every comic in the library then looks deleted at once, and acting
on that removes the rows and cascades their bookmarks away — for files
that are perfectly fine and will be back as soon as the mount is.

The delete-phase existence check cannot help here: while the mount is
gone the files genuinely are unreachable. The only defense is to notice
the shape of the failure and refuse to act, which is what both scanners
do with this.
"""

from pathlib import Path

#: Docker bind mounts of a missing host path can be seeded with this file
#: so an unmounted volume is distinguishable from an empty library.
DOCKER_UNMOUNTED_FN = "DOCKER_UNMOUNTED_VOLUME"


def unmounted_reason(root: Path) -> str:
    """Return why this library root looks unmounted, or "" if it looks fine."""
    if not root.is_dir():
        return "is not there"
    if (root / DOCKER_UNMOUNTED_FN).exists():
        return "looks like an unmounted docker volume"
    if not any(root.iterdir()):
        return "is empty. Suspect unmounted"
    return ""
