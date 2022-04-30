"""Test harness for runing individual modules."""
import os

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings.settings")

# sys.modules["haystack"] = sys.modules["codex._vendor.haystack"]

django.setup()

from codex.librarian.covers.create import recreate_all_covers  # noqa: E402


def main():
    recreate_all_covers()


if __name__ == "__main__":
    main()
