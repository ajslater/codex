#!/usr/bin/env python3
"""
groupgrep -- recursively search files for a word (default "group"),
excluding occurrences that are immediately preceded by a known prefix
plus an *optional* delimiter.

Examples it excludes (with the defaults below):
    series_group   series group   series.group   seriesgroup   series-group
    Series Group   category.group  notification group   user_group   cgroup
    authGroup   v-radio-group   v-btn-group   groupBy   group_by   grouping
    GroupAuth   GroupACLMixin   (suffix match needs no trailing boundary)
Examples it still matches:
    group   groups   subgroup   my group   foo_group   topicgroup   group-tab
    VBtnGroup (the PascalCase script form — only its kebab form is excluded)

Edit DEFAULT_PREFIXES / DEFAULT_DELIMS / DEFAULT_WORD just below, or
override any of them on the command line.
"""

import argparse
import fnmatch
import os
import sys

# ---- Configuration: edit these freely -------------------------------------
DEFAULT_WORD = "group"  # searched as a substring (so it also hits "groups")
DEFAULT_PREFIXES = [
    "link",
    "preview",
    "json",
    "series",
    "category",
    "facet",
    "channel",
    "notify",
    "notification",
    "user",
    "library",
    "auth",  # authGroup / auth-group / Authorization groups (Django auth)
    "c",  # excludes cgroup/cgroups; remove if unwanted
    # Vuetify UI grouping components (VListGroup / VBtnGroup / VRadioGroup /
    # VChipGroup / VBtnToggle group) — these are widgets, never collections.
    # Relevant for the frontend pass; harmless on the backend.
    "list",
    "btn",
    "button",
    "radio",
    "chip",
]
DEFAULT_SUFFIXES = [
    "auth",
    "acl",  # excludes group_auth, group.acl, groupauth, ...
    "by",  # excludes groupBy / group_by / group-by (lodash + SQL GROUP BY)
    "ing",  # excludes "grouping" (a generic verb, not a browse collection)
]
# The delimiter is always optional. "-" matters for the frontend: it lets the
# prefixes/suffixes match kebab-case and CSS/HTML (e.g. v-radio-group,
# series-group, group-by) the same way "_" handles snake_case.
DEFAULT_DELIMS = ["_", " ", ".", "-"]
# Directory names to skip everywhere. Glob patterns are allowed (e.g. "*_build").
# Add your own here, or pass --exclude-dir on the CLI (which adds to this list).
DEFAULT_SKIP_DIRS = [
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "static_build",
    "migrations",
    "tasks",
]
# ---------------------------------------------------------------------------


def is_excluded(line, idx, word_len, prefixes, suffixes, delims):
    """
    True if the matched word at `idx` is glued to an excluded prefix
    (before it) or suffix (after it), with an optional delimiter in between.

    Prefixes require a token boundary on their outer side (line start or a
    non-alphabetic char) so the short prefix 'c' doesn't fire on
    'topicgroup'. Suffixes don't: once the word is immediately followed by
    a suffix it's excluded regardless of what trails it — so 'group_auth',
    'group_authorize', 'GroupACLMixin', 'groupBy', and 'grouping' all drop
    while matching stays fully case-insensitive (no camelCase peeking).
    """
    before = line[:idx]
    for delim in ("", *delims):  # "" => the no-delimiter case
        if delim:
            if not before.endswith(delim):
                continue
            stem = before[: len(before) - len(delim)]
        else:
            stem = before
        for pref in prefixes:
            if stem.endswith(pref):
                start = len(stem) - len(pref)
                if start == 0 or not stem[start - 1].isalpha():
                    return True

    after = line[idx + word_len :]
    for delim in ("", *delims):
        if delim:
            if not after.startswith(delim):
                continue
            rest = after[len(delim) :]
        else:
            rest = after
        if any(rest.startswith(suf) for suf in suffixes):
            return True
    return False


def find_matches(line, word, prefixes, suffixes, delims):
    """Yield start indices of `word` in `line` that are NOT excluded."""
    pos, word_len = 0, len(word)
    while True:
        i = line.find(word, pos)
        if i == -1:
            return
        if not is_excluded(line, i, word_len, prefixes, suffixes, delims):
            yield i
        pos = i + 1


def iter_files(root, skip_dirs):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if not any(fnmatch.fnmatch(d, pat) for pat in skip_dirs)
        )
        for name in sorted(filenames):
            yield os.path.join(dirpath, name)


def read_text(path):
    """Return file text, or None if it looks binary or can't be read."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8", errors="replace")


def highlight(line, spans, word_len):
    red, reset = "\033[1;31m", "\033[0m"
    out, last = [], 0
    for s in spans:
        out.append(line[last:s])
        out.append(red + line[s : s + word_len] + reset)
        last = s + word_len
    out.append(line[last:])
    return "".join(out)


def split_list(values):
    out = []
    for v in values:
        out.extend(part for part in v.split(",") if part != "")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Recursively grep for a word, excluding prefixed forms."
    )
    ap.add_argument(
        "path",
        nargs="?",
        default=".",
        help="file or directory to search (default: current dir)",
    )
    ap.add_argument(
        "-w",
        "--word",
        default=DEFAULT_WORD,
        help=f'word to search for (default: "{DEFAULT_WORD}")',
    )
    ap.add_argument(
        "-p",
        "--prefix",
        action="append",
        metavar="LIST",
        help="prefix(es) to exclude; repeatable and/or "
        "comma-separated. Replaces the built-in list.",
    )
    ap.add_argument(
        "-S",
        "--suffix",
        action="append",
        metavar="LIST",
        help="suffix(es) to exclude; repeatable and/or "
        "comma-separated. Replaces the built-in list.",
    )
    ap.add_argument(
        "-d",
        "--delim",
        action="append",
        metavar="LIST",
        help="delimiter(s); repeatable and/or comma-separated. "
        'Use "space" or "tab" for whitespace. '
        "Replaces the built-in list.",
    )
    ap.add_argument(
        "-s",
        "--case-sensitive",
        action="store_true",
        help="case-sensitive match (default: case-insensitive)",
    )
    ap.add_argument(
        "-x",
        "--exclude-dir",
        action="append",
        metavar="LIST",
        help="director(ies) to skip; repeatable and/or "
        'comma-separated; glob patterns allowed (e.g. "*_build"). '
        "Added to the built-in skip list.",
    )
    ap.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="colorize matches (default: auto)",
    )
    args = ap.parse_args(argv)

    prefixes = split_list(args.prefix) if args.prefix else list(DEFAULT_PREFIXES)
    suffixes = split_list(args.suffix) if args.suffix else list(DEFAULT_SUFFIXES)
    if args.delim:
        whitespace = {"space": " ", "tab": "\t"}
        delims = [
            whitespace[t] if t in whitespace else t for t in split_list(args.delim)
        ]
    else:
        delims = list(DEFAULT_DELIMS)
    if not prefixes and not suffixes:
        ap.error("nothing to exclude: give at least one prefix or suffix")

    skip_dirs = list(DEFAULT_SKIP_DIRS)
    if args.exclude_dir:
        skip_dirs += split_list(args.exclude_dir)

    fold = (lambda s: s) if args.case_sensitive else str.lower
    word_cmp = fold(args.word)
    prefixes_cmp = [fold(p) for p in prefixes]
    suffixes_cmp = [fold(s) for s in suffixes]
    delims_cmp = [fold(d) for d in delims]

    use_color = (args.color == "always") or (
        args.color == "auto" and sys.stdout.isatty()
    )
    word_len = len(args.word)

    found_any = False
    for path in iter_files(args.path, skip_dirs):
        text = read_text(path)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            spans = list(
                find_matches(
                    fold(line), word_cmp, prefixes_cmp, suffixes_cmp, delims_cmp
                )
            )
            if not spans:
                continue
            found_any = True
            shown = highlight(line, spans, word_len) if use_color else line
            sys.stdout.write(f"{path}:{lineno}:{shown}\n")

    return 0 if found_any else 1


if __name__ == "__main__":
    sys.exit(main())
