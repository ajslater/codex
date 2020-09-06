"""
Manage importing, removing and moving comics in the database.

Translates between the comicbox metadata and our database model.
"""
import logging
import os

from pathlib import Path

import pycountry
import regex

from comicbox.comic_archive import ComicArchive
from django.db.models import ForeignKey
from django.db.models import ManyToManyField
from fnvhash import fnv1a_32

from codex.librarian.cover import purge_cover
from codex.librarian.queue import QUEUE
from codex.librarian.queue import ComicCoverCreateTask
from codex.librarian.queue import LibraryChangedTask
from codex.models import Comic
from codex.models import Credit
from codex.models import Folder
from codex.models import Imprint
from codex.models import Library
from codex.models import Publisher
from codex.models import Series
from codex.models import Volume


# actual filesystem route.
COMIC_MATCHER = regex.compile(r"\.cb[rz]$")
LOG = logging.getLogger(__name__)


def obj_deleted(src_path, cls):
    """Delete a class."""
    try:
        obj = cls.objects.get(path=src_path)
    except cls.DoesNotExist:
        LOG.debug(f"{cls.__name__} {src_path} does not exist. Can't delete.")
        return
    if cls == Comic:
        purge_cover(obj)
    obj.delete()
    LOG.info(f"Deleted {cls.__name__} {src_path}")
    QUEUE.put(LibraryChangedTask())


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

    obj = cls.objects.only("path", "library", "parent_folder", "folder").get(
        path=src_path
    )
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
    folders = Importer.get_folders(obj.library, obj.path)
    obj.parent_folder = folders[-1] if folders else None
    obj.folder.set(folders)

    obj.save()
    LOG.info(f"Moved {cls.__name__} from {src_path} to {dest_path}")
    QUEUE.put(LibraryChangedTask())


class Importer:
    """import ComicBox metadata into Codex database."""

    BROWSE_TREE = (Publisher, Imprint, Series, Volume)
    BROWSE_TREE_COUNT_FIELDS = {Series: "volume_count", Volume: "issue_count"}
    SPECIAL_FKS = ("myself", "volume", "series", "imprint", "publisher", "library")
    EXCLUDED_MODEL_KEYS = ("id", "parent_folder")
    FIELD_PREFIX_LEN = len("codex.Comic.")

    # Covers
    HEX_FILL = 8
    PATH_STEP = 2

    def __init__(self, library_id, path):
        """Set the state for this import."""
        self.library_id = library_id
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
        hex_path = self.hex_path()
        db_cover_path = hex_path.with_suffix(".jpg")
        task = ComicCoverCreateTask(self.path, db_cover_path)
        QUEUE.put(task)
        return db_cover_path

    @staticmethod
    def get_or_create_simple_model(name, cls):
        """Update or create a SimpleModel that just has a name."""
        if not name:
            return

        # find deleted models and undelete them too
        defaults = {}
        defaults["name"] = name
        inst, created = cls.objects.get_or_create(defaults=defaults, name__iexact=name)
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
            inst = self.get_or_create_simple_model(name, field.related_model)
            foreign_keys[field.name] = inst
        return foreign_keys

    def get_many_to_many_instances(self):
        """Get or Create all the ManyToMany fields."""
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
                    inst = self.get_or_create_simple_model(name, field.related_model)
                    if inst:
                        instances.add(inst)
                if instances:
                    m2m_fields[field.name] = instances
                del self.md[field.name]
        return m2m_fields

    def get_credits(self):
        """Get or Create credits, a complicated ManyToMany Field."""
        credits_md = self.md.get("credits")
        if not credits_md:
            return
        credits = []
        for credit_md in credits_md:
            if not credit_md:
                continue
            # Default to people credited without roles being ok.
            search = {"role": None}
            for field in Credit._meta.get_fields():
                if not isinstance(field, ForeignKey):
                    continue
                name = credit_md.get(field.name)
                if name:
                    inst = self.get_or_create_simple_model(name, field.related_model)
                    if inst:
                        search[field.name] = inst
            if len(search) != 2:
                LOG.warn(f"Invalid credit not creating: {credits_md}")
                continue
            defaults = {}
            defaults.update(search)
            credit, created = Credit.objects.get_or_create(defaults=defaults, **search)
            credits.append(credit)
            if created:
                if credit.role:
                    credit_name = credit.role.name
                else:
                    credit_name = None
                LOG.info(f"Created credit {credit_name}: {credit.person.name}")
        del self.md["credits"]
        return credits

    def get_or_create_browse_tree(self, cls, tree):
        """Get or create a single level of the comic's publish tree."""
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

        # Set all the parents from the tree we've alredy created
        for index, inst in enumerate(tree):
            field = self.BROWSE_TREE[index].__name__.lower()
            search[field] = inst

        defaults.update(search)
        if name:
            defaults["name"] = name
            search["name__iexact"] = name
        else:
            search["name__iexact"] = cls._meta.get_field("name").get_default()

        inst, created = cls.objects.get_or_create(defaults=defaults, **search)
        log_str = f"{cls.__name__} {inst.name}"
        if created:
            LOG.info(f"Created {log_str}")
        else:
            LOG.debug(f"Updated {log_str}")
        return inst

    def get_browse_containers(self):
        """Create the browse tree from publisher down to volume."""
        tree = []
        for cls in self.BROWSE_TREE:
            inst = self.get_or_create_browse_tree(cls, tree)
            tree.append(inst)
        return tree

    @staticmethod
    def get_folders(library, child_path):
        """Create db folder tree from the library on down."""
        library_p = Path(library.path)
        relative_path = Path(child_path).relative_to(library_p)

        parents = relative_path.parents
        parent_folder = None
        folder = None
        folders = []
        for parent in reversed(parents):
            if str(parent) == ".":
                continue
            path = library_p / parent
            defaults = {"name": path.name, "parent_folder": parent_folder}
            search_kwargs = {
                "library": library,
                "path": str(path),
            }
            defaults.update(search_kwargs)
            folder, created = Folder.objects.get_or_create(
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
        created = False
        try:
            (
                self.md["publisher"],
                self.md["imprint"],
                self.md["series"],
                self.md["volume"],
            ) = self.get_browse_containers()
            library = Library.objects.only("pk", "path").get(pk=self.library_id)
            self.set_locales()
            credits = self.get_credits()
            m2m_fields = self.get_many_to_many_instances()
            self.clean_metadata()  # the order of this is pretty important
            foreign_keys = self.get_foreign_keys()
            self.md.update(foreign_keys)
            folders = self.get_folders(library, self.path)
            if folders:
                self.md["parent_folder"] = folders[-1]
            self.md["library"] = library
            self.md["path"] = self.path
            self.md["size"] = Path(self.path).stat().st_size
            self.md["max_page"] = max(self.md["page_count"] - 1, 0)
            cover_path = self.get_cover_path()
            if cover_path:
                self.md["cover_path"] = cover_path

            if credits:
                m2m_fields["credits"] = credits
            m2m_fields["folder"] = folders
            comic, created = Comic.objects.update_or_create(
                defaults=self.md, path=self.path
            )
            comic.myself = comic

            # Add the m2m2 instances afterwards, can't initialize with them
            for attr, instance_list in m2m_fields.items():
                getattr(comic, attr).set(instance_list)
            comic.save()

            if created:
                verb = "Created"
            else:
                verb = "Updated"
            LOG.info(f"{verb} comic {str(comic.volume.series.name)} #{comic.issue:03}")
            QUEUE.put(LibraryChangedTask())
        except Exception as exc:
            LOG.exception(exc)
        return created


def import_comic(library_id, path):
    """Import a single comic."""
    importer = Importer(library_id, path)
    importer.import_metadata()
