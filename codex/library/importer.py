"""
Manage importing, removing and moving comics in the database.

Translates between the comicbox metadata and our database model.
"""
import logging

from copy import deepcopy
from io import BytesIO
from pathlib import Path

import regex

from django.db.models import ForeignKey
from django.db.models import ManyToManyField
from PIL import Image

from codex.models import Comic
from codex.models import Credit
from codex.models import Imprint
from codex.models import Publisher
from codex.models import Series
from codex.models import Volume
from comicbox.comic_archive import ComicArchive


COVER_ROOT = Path("./codex/static/codex/covers")
THUMBNAIL_WIDTH = 180  # 120
THUMBNAIL_HEIGHT = 180
THUMBNAIL_SIZE = (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)

PUBLISH_TREE = (Publisher, Imprint, Series, Volume)
PT_COUNT_FIELDS = {Series: "volume_count", Volume: "issue_count"}

COMIC_MATCHER = regex.compile(r"\.cb[rz]$")
UNDELETE = {"deleted_at": None}

CREDIT_KEYS = ("person", "role")
FIELD_PREFIX_LEN = len("codex.Comic.")

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
HEX_FILL = 8
PATH_STEP = 2


def hex_path(root, integer, ext):
    """Translate an integer into an efficient filesystem path."""
    hex_str = "{0:0{1}x}".format(integer, HEX_FILL)
    parts = []
    for i in range(0, len(hex_str), PATH_STEP):
        parts.append(hex_str[i : i + PATH_STEP])
    path = COVER_ROOT / Path("/".join(parts) + ext)
    return path


def get_cover_path(comic_id):
    """Get path to a cover image, creating the image if not found."""
    cover_path = hex_path(COVER_ROOT, comic_id, ".jpg")
    if not cover_path.is_file():
        comic = Comic.objects.get(pk=comic_id)
        car = ComicArchive(comic.path)
        im = Image.open(BytesIO(car.get_cover_image()))
        im.thumbnail(THUMBNAIL_SIZE)
        cover_path.parent.mkdir(exist_ok=True, parents=True)
        im.save(cover_path, im.format)
        LOG.debug(f"Cached cover for: {comic.name}")
    return cover_path


def get_comic_metadata(path):
    """Get comic metadata with ComicBox."""
    search = COMIC_MATCHER.search(str(path))
    if not search:
        LOG.debug(f"{path} is not a comic archive.")
        return

    car = ComicArchive(path)
    md = car.get_metadata()
    return md


def update_or_create_simple_model(name, cls):
    """Update or create a SimpleModel that just has a name."""
    if not name:
        return

    # find deleted models and undelete them too
    defaults = deepcopy(UNDELETE)
    defaults["name"] = name
    inst, created = cls.objects.update_or_create(defaults=defaults, name__iexact=name)
    if created:
        LOG.info(f"Created {cls.__name__} {inst.name}")
    return inst


def get_foreign_keys(metadata):
    """Set all the foreign keys in the comic model."""
    foreign_keys = {}
    for field in Comic._meta.get_fields():
        if not isinstance(field, ForeignKey):
            continue
        if field.name in ("volume", "root_path"):
            continue
        name = metadata.get(field.name)
        inst = update_or_create_simple_model(name, field.related_model)
        foreign_keys[field.name] = inst
    return foreign_keys


def get_many_to_many_instances(metadata):
    """Create or update all the ManyToMany fields."""
    m2m_fields = {}
    # for key, cls, in M2M_KEYS.items():
    for field in Comic._meta.get_fields():
        if not isinstance(field, ManyToManyField):
            continue
        if field.name == "credits":
            continue
        names = metadata.get(field.name)
        if names:
            instances = set()
            for name in names:
                inst = update_or_create_simple_model(name, field.related_model)
                if inst:
                    instances.add(inst)
            if instances:
                m2m_fields[field.name] = instances
            del metadata[field.name]
    return m2m_fields


def get_credits(metadata):
    """Create or update credits, a complicated ManyToMany Field."""
    credits_md = metadata.get("credits")
    if not credits_md:
        return
    credits = []
    for credit_md in credits_md:
        if not credit_md:
            continue
        search = {}
        for field in Credit._meta.get_fields():
            if not isinstance(field, ForeignKey):
                continue
            name = credit_md.get(field.name)
            if name:
                inst = update_or_create_simple_model(name, field.related_model)
                if inst:
                    search[field.name] = inst
        defaults = deepcopy(UNDELETE)
        defaults.update(search)
        credit, created = Credit.objects.update_or_create(defaults=defaults, **search)
        credits.append(credit)
        if created:
            LOG.info(f"Created credit {credit.role.name}: {credit.person.name}")
    del metadata["credits"]
    return credits


def update_or_create_publish_tree(metadata, cls, parent):
    """Update or create a single level of the comic's publish tree."""
    key = cls.__name__.lower()  # current level
    name = metadata.get(key)  # name of the current level
    search = {}
    defaults = {}
    if name:
        for key, val in PT_COUNT_FIELDS.items():
            # set special metadata keys for the level we're at
            if isinstance(cls, key):
                defaults[val] = metadata.get(val)
                break
            search["is_default"] = False
    else:
        # current level has no name, so make a default one
        name = cls.DEFAULT_NAME
        search["is_default"] = True

    # Set the parent
    if cls != Publisher:
        # Publishers don't have parents
        search[cls.PARENT_FIELD] = parent
    defaults.update(search)
    defaults["name"] = name
    search["name__iexact"] = name
    inst, created = cls.objects.update_or_create(defaults=defaults, **search)
    log_str = f"ed {cls.__name__} {inst.name}"
    if created:
        LOG.info(f"Creat{log_str}")
    else:
        LOG.debug(f"Updat{log_str}")
    return inst


def get_publish_tree(metadata):
    """Create the publish tree from publisher root down to volume."""
    parent = None
    for cls in PUBLISH_TREE:
        inst = update_or_create_publish_tree(metadata, cls, parent)
        parent = inst
    return inst


def clean_metadata(metadata):
    """Create whitelisted metdata object with only Comic model fields."""
    fields = Comic._meta.fields
    clean_md = {}
    for field in fields:
        key = str(field)[FIELD_PREFIX_LEN:]
        if key != "id" and key in metadata.keys():
            clean_md[key] = metadata[key]
    return clean_md


def import_comic(root_path, path):
    """Import a comic into the db, from a path, using Comicbox."""
    md = get_comic_metadata(path)
    if not md:
        return
    md["volume"] = get_publish_tree(md)
    md = clean_metadata(md)
    foreign_keys = get_foreign_keys(md)
    md.update(foreign_keys)
    md["root_path"] = root_path
    md["path"] = path
    md["deleted_at"] = None  # undeletes a previously stored comic

    m2m_fields = get_many_to_many_instances(md)
    credits = get_credits(md)
    if credits:
        m2m_fields["credits"] = credits

    comic, created = Comic.objects.update_or_create(defaults=md, path=path)
    # Add the m2m2 instances afterwards, can't initialize with them
    for attr, instance_list in m2m_fields.items():
        getattr(comic, attr).set(instance_list)
    comic.save()
    if created:
        verb = "Created"
    else:
        verb = "Updated"
    LOG.info(f"{verb} comic {str(comic.volume.series.name)} #{comic.issue:03}")
    return created
