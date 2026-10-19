"""Give every pytest process its own CODEX_CONFIG_DIR before Django loads."""

import os

from tests.tmp_dirs import tmp_dir

# Registered with ``-p`` in ``addopts`` because pytest-django imports the
# settings in ``pytest_load_initial_conftests``, before ``conftest.py`` loads;
# ``-p`` modules import earlier, during option pre-parsing.
#
# Without this every run shares ``./config``: the developer's real config,
# and above all its file-based Django caches. Under xdist, cachalot then
# serves one worker's cached queries to the others, each of which has its
# own in-memory test database, and test-DB setup fails with ``UNIQUE
# constraint failed: django_content_type...``. ``cache.clear()`` in one
# worker would also wipe the others' entries.
#
# xdist workers inherit the controller's environment, so a worker always
# replaces the inherited value. A serial run keeps an explicit
# CODEX_CONFIG_DIR.
if "PYTEST_XDIST_WORKER" in os.environ or "CODEX_CONFIG_DIR" not in os.environ:
    _config_dir = tmp_dir("config")
    # Settings write the secret key files straight into it at import.
    _config_dir.mkdir(exist_ok=True)
    os.environ["CODEX_CONFIG_DIR"] = str(_config_dir)
