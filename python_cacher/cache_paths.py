"""Find the cache path for this architecture."""
import platform
from pathlib import Path

LINUX_CACHE_PATH = ".cache"
MACOS_CACHE_PATH = "Library/Caches"


system = platform.system()
if system == "Darwin":
    CACHE_PATH = Path.home() / MACOS_CACHE_PATH
else:  # system == "Linux":
    CACHE_PATH = Path.home() / LINUX_CACHE_PATH

POETRY_CACHE_PATH = CACHE_PATH / "pypoetry"
PIP_CACHE_PATH = CACHE_PATH / "pip"
POETRY_ARTIFACTS_PATH = POETRY_CACHE_PATH / "artifacts"
PIP_WHEELS_PATH = PIP_CACHE_PATH / "wheels"
