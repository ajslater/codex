"""
Tell "nothing is there" apart from "I could not look".

Both scanners and the importer's delete backstop have to decide whether a
path that did not answer is really gone. Only two errors say so: ``ENOENT``
(no such file) and ``ENOTDIR`` (a path component is not a directory, so the
name cannot exist). Python raises those as ``FileNotFoundError`` and
``NotADirectoryError``.

Every other ``OSError`` — ``EACCES``/``EPERM`` on a locked directory,
``EIO``/``ESTALE``/``ETIMEDOUT`` on a network share that dropped — means the
answer is unknown. Treating unknown as gone deletes comic rows whose files
are fine, and ``Bookmark.comic`` cascades the user's read progress away with
them. Anything that cannot prove absence must fail closed.

``Path.exists()`` cannot make this distinction: it swallows every
``OSError`` and returns ``False``, which is exactly how a briefly unreadable
directory used to read as a mass deletion.
"""

#: Errors that prove a path is not there. Catch these before a bare
#: ``except OSError`` wherever absence drives a delete.
GONE_ERRORS = (FileNotFoundError, NotADirectoryError)
