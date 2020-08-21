"""Manage importing, removing and moving comics in the database."""
import logging

import regex

from comicbox.comic_archive import ComicArchive

from . import models


LOG = logging.getLogger(__name__)

COMIC_MATCHER = regex.compile(r"\.cb[rz]$")


def import_comic(path):
    if not COMIC_MATCHER.match(path):
        LOG.debug(f"{path} is not a comic archive.")

    car = ComicArchive(path)
    md = car.get_metadata()
    comic = models.Comic(md)
    comic.save()


def comic_removed(path):
    car = ComicArchive(path)
    car.path = None
