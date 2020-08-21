"""
Manage importing, removing and moving comics in the database.

Translates between the comicbox metadata and our database model.
"""
import logging
import os

from io import BytesIO
from pathlib import Path

import pycountry
import regex

from django.db.models import ForeignKey
from django.db.models import ManyToManyField
from fnvhash import fnv1a_32
from PIL import Image

from codex.models import Comic
from codex.models import Credit
from codex.models import Folder
from codex.models import Imprint
from codex.models import Publisher
from codex.models import RootPath
from codex.models import Series
from codex.models import Volume
from codex.settings import STATIC_ROOT
from comicbox.comic_archive import ComicArchive


# actual filesystem route.
FS_STATIC_PREFIX = Path("codex") / STATIC_ROOT

COMIC_MATCHER = regex.compile(r"\.cb[rz]$")

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


def obj_deleted(src_path, cls):
    """Delete a class."""
    try:
        obj = cls.objects.get(path=src_path)
    except cls.DoesNotExist:
        LOG.debug(f"{cls.__name__} {src_path} does not exist. Can't delete.")
        return
    if cls == Comic:
        cover_path = FS_STATIC_PREFIX / obj.cover_path
        try:
            # TODO python 3.8 missing_ok=True
            cover_path.unlink()
        except FileNotFoundError:
            pass
    obj.delete()
    LOG.info(f"Deleted {cls.__name__} {src_path}")


def does_folder_contain_comics(path):
    """Only pay attention to folders with comics in them."""
    for root, _, fns in os.walk(path):
        rp = Path(root)
        for fn in fns:
            fpath = rp / fn
            if COMIC_MATCHER.search(str(fpath)) is not None:
                return True

    return False


def obj_moved(src_path, dest_path, cls):
    """Move a comic in the db."""
    if cls == Folder and not does_folder_contain_comics(dest_path):
        LOG.debug(f"Ignoring {dest_path} folder without comics.")
        return

    obj = cls.objects.get(path=src_path)
    if cls.objects.filter(path=dest_path).exists():
        """
        Files get moved before folders which means they create new folders
        before we can move the old one, leaving the folder orphaned. So we
        delete it. This means we create a lot of new folder objects. The
        solution for this is to implement an event aggregation queue in
        watcherd and handle a big folder move as one event.
        """

        obj_deleted(src_path, cls)
        LOG.debug(
            f"Deleted {cls.__name__} {src_path} becuase {dest_path} already exists."
        )
        return
    obj.path = dest_path
    folders = Importer.get_folders(obj.root_path, obj.path)
    obj.parent_folder = folders[-1] if folders else None
    obj.folder.set(folders)

    obj.save()
    LOG.info(f"Moved {cls.__name__} from {src_path} to {dest_path}")


class Importer:
    """import ComicBox metadata into Codex database."""

    BROWSE_TREE = (Publisher, Imprint, Series, Volume)
    BROWSE_TREE_COUNT_FIELDS = {Series: "volume_count", Volume: "issue_count"}
    SPECIAL_FKS = ("volume", "series", "imprint", "publisher", "root_path")
    EXCLUDED_MODEL_KEYS = ("id", "parent_folder")
    FIELD_PREFIX_LEN = len("codex.Comic.")

    # Covers
    HEX_FILL = 8
    PATH_STEP = 2
    COVER_ROOT = Path("covers")
    THUMBNAIL_SIZE = (180, 180)

    def __init__(self, root_path_id, path):
        """Set the state for this import."""
        self.root_path_id = root_path_id
        self.path = path
        self.car = ComicArchive(path)
        self.md = self.car.get_metadata()

    def hex_path(self):
        """Translate an integer into an efficient filesystem path."""
        fnv = fnv1a_32(bytes(str(self.path), "utf-8"))
        hex_str = "{0:0{1}x}".format(fnv, self.HEX_FILL)
        parts = []
        for i in range(0, len(hex_str), self.PATH_STEP):
            parts.append(hex_str[i : i + self.PATH_STEP])
        path = Path("/".join(parts))
        return path

    def get_cover_path(self):
        """Get path to a cover image, creating the image if not found."""
        cover_path = self.COVER_ROOT / self.hex_path()
        try:
            im = Image.open(BytesIO(self.car.get_cover_image()))
            im.thumbnail(self.THUMBNAIL_SIZE)
            db_cover_path = cover_path.with_suffix("." + im.format.lower())
            fs_cover_path = FS_STATIC_PREFIX / db_cover_path
            fs_cover_path.parent.mkdir(exist_ok=True, parents=True)
            im.save(fs_cover_path, im.format)
            LOG.debug(f"Cached cover for: {self.path}")
        except Exception as exc:
            LOG.exception(exc)
            LOG.error(f"Failed to create cover thumb for {self.path}")
            return None
        return db_cover_path

    @staticmethod
    def update_or_create_simple_model(name, cls):
        """Update or create a SimpleModel that just has a name."""
        if not name:
            return

        # find deleted models and undelete them too
        defaults = {}
        defaults["name"] = name
        inst, created = cls.objects.update_or_create(
            defaults=defaults, name__iexact=name
        )
        if created:
            LOG.info(f"Created {cls.__name__} {inst.name}")
        return inst

    def get_foreign_keys(self):
        """Set all the foreign keys in the comic model."""
        foreign_keys = {}
        for field in Comic._meta.get_fields():
            if not isinstance(field, ForeignKey):
                continue
            if field.name in self.SPECIAL_FKS:
                continue
            name = self.md.get(field.name)
            inst = self.update_or_create_simple_model(name, field.related_model)
            foreign_keys[field.name] = inst
        return foreign_keys

    def get_many_to_many_instances(self):
        """Create or update all the ManyToMany fields."""
        m2m_fields = {}
        # for key, cls, in M2M_KEYS.items():
        for field in Comic._meta.get_fields():
            if not isinstance(field, ManyToManyField):
                continue
            if field.name == "credits":
                continue
            names = self.md.get(field.name)
            if names:
                instances = set()
                for name in names:
                    inst = self.update_or_create_simple_model(name, field.related_model)
                    if inst:
                        instances.add(inst)
                if instances:
                    m2m_fields[field.name] = instances
                del self.md[field.name]
        return m2m_fields

    def get_credits(self):
        """Create or update credits, a complicated ManyToMany Field."""
        credits_md = self.md.get("credits")
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
                    inst = self.update_or_create_simple_model(name, field.related_model)
                    if inst:
                        search[field.name] = inst
            defaults = {}
            defaults.update(search)
            credit, created = Credit.objects.update_or_create(
                defaults=defaults, **search
            )
            credits.append(credit)
            if created:
                LOG.info(f"Created credit {credit.role.name}: {credit.person.name}")
        del self.md["credits"]
        return credits

    def update_or_create_browse_tree(self, cls, parent):
        """Update or create a single level of the comic's publish tree."""
        md_key = cls.__name__.lower()  # current level
        name = self.md.get(md_key)  # name of the current level
        defaults = {}
        if name:
            for key, val in self.BROWSE_TREE_COUNT_FIELDS.items():
                # set special total count fields for the level we're at
                if isinstance(cls, key):
                    defaults[val] = self.md.get(val)
                    break
        search = {"is_default": name is not None}

        # Set the parent
        if cls != Publisher:
            # Publishers don't have parents
            search[cls.PARENT_FIELD] = parent
        defaults.update(search)
        if name:
            defaults["name"] = name
            search["name__iexact"] = name
        else:
            search["name__iexact"] = cls._meta.get_field("name").get_default()

        inst, created = cls.objects.update_or_create(defaults=defaults, **search)
        log_str = f"{cls.__name__} {inst.name}"
        if created:
            LOG.info(f"Created {log_str}")
        else:
            LOG.debug(f"Updated {log_str}")
        return inst

    def get_browse_containers(self):
        """Create the browse tree from publisher down to volume."""
        parent = None
        tree = []
        for cls in self.BROWSE_TREE:
            inst = self.update_or_create_browse_tree(cls, parent)
            tree.append(inst)
            parent = inst
        return tree

    @staticmethod
    def get_folders(root_path, child_path):
        """Create db folder tree from the root path on down."""
        root_path_p = Path(root_path.path)
        relative_path = Path(child_path).relative_to(root_path_p)

        parents = relative_path.parents
        parent_folder = None
        folder = None
        folders = []
        for parent in reversed(parents):
            if str(parent) == ".":
                continue
            path = root_path_p / parent
            defaults = {"name": path.name, "parent_folder": parent_folder}
            search_kwargs = {
                "root_path": root_path,
                "path": str(path),
            }
            defaults.update(search_kwargs)
            folder, created = Folder.objects.update_or_create(
                defaults=defaults, **search_kwargs
            )
            if created:
                LOG.info(f"Created {path} db folder.")
            parent_folder = folder
            folders.append(folder)
        return folders

    def clean_metadata(self):
        """Create whitelisted metdata object with only Comic model fields."""
        fields = Comic._meta.fields
        clean_md = {}
        for field in fields:
            key = str(field)[self.FIELD_PREFIX_LEN :]
            if key not in self.EXCLUDED_MODEL_KEYS and key in self.md.keys():
                clean_md[key] = self.md[key]
        self.md = clean_md

    def set_locales(self):
        """Explode locale info from alpha2 into long names."""
        # Could do i8n here later
        lang = self.md.get("language")
        if lang:
            pc_lang = pycountry.languages.lookup(lang)
            if pc_lang:
                self.md["language"] = pc_lang.name
        country = self.md.get("country")
        if country:
            py_country = pycountry.countries.lookup(country)
            if py_country:
                self.md["country"] = py_country.name

    def import_metadata(self):
        """Import a comic into the db, from a path, using Comicbox."""
        # Buld the catalogue tree BEFORE we clean the metadata
        try:
            (
                self.md["publisher"],
                self.md["imprint"],
                self.md["series"],
                self.md["volume"],
            ) = self.get_browse_containers()
            root_path = RootPath.objects.get(pk=self.root_path_id)
            self.set_locales()
            credits = self.get_credits()
            m2m_fields = self.get_many_to_many_instances()
            self.clean_metadata()  # the order of this is pretty important
            foreign_keys = self.get_foreign_keys()
            self.md.update(foreign_keys)
            folders = self.get_folders(root_path, self.path)
            if folders:
                self.md["parent_folder"] = folders[-1]
            self.md["root_path"] = root_path
            self.md["path"] = self.path
            self.md["size"] = Path(self.path).stat().st_size
            cover_path = self.get_cover_path()
            if cover_path:
                self.md["cover_path"] = cover_path

            if credits:
                m2m_fields["credits"] = credits
            m2m_fields["folder"] = folders
            comic, created = Comic.objects.update_or_create(
                defaults=self.md, path=self.path
            )
            comic.comic = comic

            # Add the m2m2 instances afterwards, can't initialize with them
            for attr, instance_list in m2m_fields.items():
                getattr(comic, attr).set(instance_list)
            comic.save()
            if created:
                verb = "Created"
            else:
                verb = "Updated"
            LOG.info(f"{verb} comic {str(comic.volume.series.name)} #{comic.issue:03}")
        except Exception as exc:
            LOG.exception(exc)
            created = False
        return created


def import_comic(root_path_id, path):
    """Import a single comic."""
    importer = Importer(root_path_id, path)
    importer.import_metadata()
