"""
Force Fork style multiprocessing on Darwin.

Fixes LIBRARIAN_QUEUE sharing and haystack update_index() with default
macOS spawn start method.
The spawn method is also very very slow. Use fork and the
OBJC_DISABLE_INITIALIZE_FORK_SAFETY environment variable for macOS.

This must be run in the main process before the we create the Librarian process
And in the Librarian db updater thread before the haystack update_index()
command is run.

Relevant Bugs:
https://bugs.python.org/issue40106
https://github.com/django-haystack/django-haystack/issues/1650
"""
import os
import platform


def force_darwin_multiprocessing_fork():
    """Force Darwin to use fork."""
    if platform.system() == "Darwin":
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
        from multiprocessing import set_start_method

        set_start_method("fork", force=True)
