"""
Manage importing, removing and moving comics in the database.

Translates between the comicbox metadata and our database model.
"""
import logging
import os
import re

from pathlib import Path

import pycountry

from comicbox.comic_archive import ComicArchive
from django.db.models import ForeignKey, ManyToManyField

from codex.librarian.cover import get_cover_path, purge_cover
from codex.librarian.queue import QUEUE, ComicCoverCreateTask, LibraryChangedTask
from codex.models import (
    Comic,
    Credit,
    FailedImport,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.settings.settings import DEBUG


# actual filesystem route.
COMIC_MATCHER = re.compile(r"\.cb[rz]$")
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

    BROWSER_GROUP_TREE = (Publisher, Imprint, Series, Volume)
    BROWSER_GROUP_TREE_COUNT_FIELDS = {Series: "volume_count", Volume: "issue_count"}
    SPECIAL_FKS = ("myself", "volume", "series", "imprint", "publisher", "library")
    EXCLUDED_MODEL_KEYS = ("id", "parent_folder")
    FIELD_PREFIX_LEN = len("codex.Comic.")

    def __init__(self, library_id, path):
        """Set the state for this import."""
        self.library_id = library_id
        self.path = path
        self.car = ComicArchive(path)
        self.md = self.car.get_metadata()

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

    def get_or_create_browser_group_tree(self, cls, tree):
        """Get or create a single level of the comic's publish tree."""
        md_key = cls.__name__.lower()  # current level
        name = self.md.get(md_key)  # name of the current level
        defaults = {}
        if name:
            for key, val in self.BROWSER_GROUP_TREE_COUNT_FIELDS.items():
                # set special total count fields for the level we're at
                if isinstance(cls, key):
                    defaults[val] = self.md.get(val)
                    break
        search = {"is_default": name is not None}

        # Set all the parents from the tree we've alredy created
        for index, inst in enumerate(tree):
            field = self.BROWSER_GROUP_TREE[index].__name__.lower()
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

    def get_browser_group_tree(self):
        """Create the browse tree from publisher down to volume."""
        tree = []
        for cls in self.BROWSER_GROUP_TREE:
            inst = self.get_or_create_browser_group_tree(cls, tree)
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
        (
            self.md["publisher"],
            self.md["imprint"],
            self.md["series"],
            self.md["volume"],
        ) = self.get_browser_group_tree()
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
        cover_path = get_cover_path(self.path)
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
        QUEUE.put(ComicCoverCreateTask(self.path, str(cover_path), True))

        # If it works, clear the failed import
        FailedImport.objects.filter(path=self.path).delete()

        if created:
            verb = "Created"
        else:
            verb = "Updated"
        LOG.info(f"{verb} comic {str(comic.volume.series.name)} #{comic.issue:03}")
        QUEUE.put(LibraryChangedTask())
        return created


def import_comic(library_id, path):
    """Import a single comic."""
    try:
        importer = Importer(library_id, path)
        importer.import_metadata()
    except Exception as exc:
        library = Library.objects.get(pk=library_id)
        path_str = str(path)
        search_kwargs = {"library": library, "path": path_str}
        reason = FailedImport.get_reason(exc, path_str)
        defaults = {"reason": reason}
        defaults.update(search_kwargs)
        fi, fi_created = FailedImport.objects.update_or_create(
            defaults=defaults, **search_kwargs
        )
        LOG.warn(f"Import failed: {path_str} {reason}")
        if DEBUG:
            LOG.exception(exc)
