"""
Parse comic book archive names using the simple 'parse' parser.

A more sophisticaed libarary like pyparsing or rebulk might be able to
build a faster, more powerful matching engine with fewer parsers with
optional fields. But this brute force method with the parse library is
effective, simple and easy to read and to contribute to.
"""

from pathlib import Path

import regex

from parse import compile

from comicbox.metadata.comic_base import ComicBaseMetadata


def compile_parsers(patterns):
    """Compile patterns into parsers without spewing debug logs."""
    from logging import getLogger

    log = getLogger("parse")
    old_level = log.level
    log.setLevel("INFO")
    parsers = tuple([compile(pattern) for pattern in patterns])
    log.setLevel(old_level)
    return parsers


class FilenameMetadata(ComicBaseMetadata):
    """Extract metdata from the filename."""

    ALL_FIELDS = set(["series", "volume", "issue", "issue_count", "year", "ext"])
    FIELD_SCHEMA = {key: None for key in ALL_FIELDS}
    # The order of these patterns is very important as patterns farther down
    # the list are more permissive than those higher up.
    PATTERNS = (
        "{series} v{volume:d} {issue:3d} {title} ({year:4d}) {remainder}.{ext}",
        "{series} v{volume:d} {title} ({year:4d}) {remainder}.{ext}",
        "{series} {issue:d} ({year:4d}) {remainder}.{ext}",
        "{series} {issue:d} (of {issue_count:d}) ({year:4d}) {remainder}.{ext}",
        "{series} v{volume:d} {title} ({year:4d}) {remainder}.{ext}",
        "{series} v{volume:d} {issue:d} {title} ({year:4d}) {remainder}.{ext}",
        "{series} v{volume:d} ({year:4d}) #{issue:d} {title} {remainer}.{ext}",
        "{series} Vol {volume:d}{garbage}({year:4d}) {remainder}.{ext}",
        "{series} Vol. {volume:d} {title} ({year:4d}) {remainder}.{ext}",
        "{series} v{volume:d} ({year:4d}) {remainder}.{ext}",
        "{series} v{volume:d} ({year:4d}) {issue:d} {remainder}.{ext}",
        "{series} v{volume:d} ({year:4d}) #{issue:d} {remainder}.{ext}",
        "{series} v{volume:d} {issue:d} {title} ({year:4d}) {remainder}.{ext}"
        "{series} v{volume:d} {title} ({year:4d}) {remainder}.{ext}"
        "{series} {issue:d} (of {issue_count:d}) ({year:4d}) {remainder}.{ext}",
        "{series} {issue:d} (of {issue_count:d}) {remainder}.{ext}",
        "{series} ({issue:d} of {issue_count:d}) ({year:4d}) {remainder}.{ext}",
        "{series} ({issue:d} of {issue_count:d}) {remainder}.{ext}",
        "{series} {issue:d} ({year:4d}) {remainder}.{ext}",
        "{series} #{issue:d} ({year:4d}) {remainder}.{ext}",
        "{series} ({year:4d}) {issue:d} {remainder}.{ext}",
        "{series} ({year:4d}) #{issue:d} {remainder}.{ext}",
        "{issue:d} {series} {remainder}.{ext}",
        "{series} ({year:4d}) {remainder}.{ext}",
        "{series} {issue:d} {remainder}.{ext}",
        "{series} {issue:d}.{ext}",
        "{series} #{issue:d} {remainder}.{ext}",
        "{series} #{issue:d}.{ext}",
        "{series}.{ext}",
        "{issue:d} {series}.{ext}",
    )

    PATTERN_MAX_MATCHES = tuple([pattern.count("}") for pattern in PATTERNS])
    PARSERS = compile_parsers(PATTERNS)
    SPACE_ALT_CHARS_RE = regex.compile(r"[_-]+")
    PLUS_RE = regex.compile(r"\++")
    MULTI_SPACE_RE = regex.compile(r"\s{2,}")
    FILENAME_TAGS = (
        ("series", "{}"),
        ("volume", "v{}"),
        ("issue", "#{:03}"),
        ("issue_count", "(of {:03})"),
        ("year", "({})"),
        ("title", "{}"),
    )

    def clean_fn(self, filename):
        """Clean out distracting characters from the filename."""
        fn = self.SPACE_ALT_CHARS_RE.sub(" ", filename)
        fn = self.PLUS_RE.sub(" ", fn)
        fn = self.MULTI_SPACE_RE.sub(" ", fn)
        return fn

    @staticmethod
    def try_parser(parser, fn):
        """Try one parser and return the results as a dict."""
        res = parser.parse(fn)
        if res:
            return res.named
        return {}

    def from_string(self, path):
        """Try all parsers againts the filename and return the best result."""
        self._path = Path(path)
        fn = self.clean_fn(self._path.name)
        best_res = {}
        pattern_num = 0
        for parser in self.PARSERS:
            res = self.try_parser(parser, fn)
            if len(res) > len(best_res):
                best_res = res
                if len(best_res) == self.PATTERN_MAX_MATCHES[pattern_num]:
                    # if we match everything in the pattern end early.
                    break
            pattern_num += 1
        self.metadata.update(best_res)

    def from_file(self, path):
        """Oddly this ends up being identical."""
        return self.from_string(path)

    def to_string(self):
        """Get our preferred basename from a metadata dict."""
        tokens = []
        for tag, fmt in self.FILENAME_TAGS:
            val = self.metadata.get(tag)
            if val:
                token = fmt.format(val)
                tokens.append(token)
        name = " ".join(tokens)
        return name

    def to_file(self, path):
        """Rename this file according to our favorite naming scheme."""
        name = self.to_string()
        new_path = path.parent / Path(name + path.suffix)
        old_path = path
        path.rename(new_path)
        print(f"Renamed:\n{old_path} ==> {self._path}")
        return new_path
