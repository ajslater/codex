#!/usr/bin/env python3
"""Cli for comicbox."""
import argparse
import os
import sys

from pathlib import Path
from pprint import pprint

from .comic_archive import VERSION
from .comic_archive import ComicArchive


def get_args():
    """Get arguments and options."""
    description = "Comic book archive read/write tool."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "path", type=Path, help="Path to the comic archive",
    )
    parser.add_argument("-p", "--metadata", action="store_true", help="Print metadata")
    parser.add_argument("-v", "--version", action="store_true", help="Display version.")
    parser.add_argument(
        "-R",
        "--ignore-comicrack",
        action="store_false",
        dest="comicrack",
        default=True,
        help="Ignore ComicRack metadata if present.",
    )
    parser.add_argument(
        "-L",
        "--ignore-comiclover",
        action="store_false",
        dest="comiclover",
        default=True,
        help="Ignore ComicLover metadata if present.",
    )
    parser.add_argument(
        "-C",
        "--ignore-comet",
        action="store_false",
        dest="comet",
        default=True,
        help="Ignore CoMet metadata if present.",
    )
    parser.add_argument(
        "-F",
        "--ignore-filename",
        action="store_false",
        dest="filename",
        default=True,
        help="Ignore filename metadata.",
    )
    parser.add_argument(
        "-f",
        "--from",
        dest="index_from",
        type=int,
        help="Extract pages from the specified index forward.",
    )
    parser.add_argument(
        "-d",
        "--dest_path",
        default=".",
        type=Path,
        help="destination path for extracting pages and metadata.",
    )
    parser.add_argument(
        "-c", "--covers", action="store_true", help="Extract cover pages."
    )
    parser.add_argument(
        "-r", "--raw", action="store_true", help="Print raw metadata without parsing"
    )
    parser.add_argument(
        "-z", "--cbz", action="store_true", help="Export the archive to CBZ format."
    )
    parser.add_argument(
        "--delete-rar",
        action="store_true",
        help="Delete the original rar file if the zip is exported sucessfully.",
    )
    parser.add_argument(
        "-i",
        "--import",
        action="store",
        dest="import_fn",
        help="Import metadata from an external file.",
    )
    parser.add_argument(
        "-e",
        "--export",
        action="store_true",
        help="Export metadata as external files in several formats.",
    )
    parser.add_argument(
        "--rename",
        action="store_true",
        help="Rename the file with our preferred schema.",
    )
    parser.add_argument(
        "--delete", action="store_true", help="Delete all tags from archive."
    )
    parser.add_argument(
        "--recurse",
        action="store_true",
        help="Perform seletced actions recursively on a directory.",
    )

    return parser.parse_args()


def run_on_file(args, path):
    """Run operations on one file."""
    if not args.path.is_file():
        print("{args.path} is not a file.")

    car = ComicArchive(path, settings=args)
    if args.raw:
        car.print_raw()
    elif args.metadata:
        pprint(car.get_metadata())
    elif args.covers:
        car.extract_cover_as(args.dest_path)
    elif args.index_from:
        car.extract_pages(args.index_from, args.dest_path)
    elif args.export:
        car.export_files()
    elif args.delete:
        car.delete_tags()
    elif args.cbz:
        car.recompress(delete_rar=True)
    elif args.import_fn:
        car.import_file(args.import_fn)
    elif args.rename:
        car.rename_file()
    else:
        print("Nothing to do.")


def recurse(args, path):
    """Perform operations recursively on files."""
    if not path.is_dir():
        print(f"{path} is not a directory")
        sys.exit(1)

    for root, _, filenames in os.walk(path):
        root_path = Path(root)
        for filename in sorted(filenames):
            full_path = root_path / filename
            run_on_file(args, full_path)


def main():
    """Get CLI arguments and perform the operation on the archive."""
    args = get_args()
    if args.version:
        print(VERSION)
        return

    if not args.recurse:
        run_on_file(args, args.path)
    else:
        recurse(args, args.path)


if __name__ == "__main__":
    main()
