"""
Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""

from logging import getLogger
from pathlib import Path

from django.db.models.functions import Now

from codex.models import (
    Credit,
    CreditPerson,
    CreditRole,
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
)


BULK_UPDATE_FOLDER_MODIFIED_FIELDS = ("stat", "updated_at")
LOG = getLogger(__name__)


def _create_group_obj(cls, group_param_tuple, count):
    """Create a set of browser group objects."""
    defaults = {"name": group_param_tuple[-1]}
    if cls in (Imprint, Series, Volume):
        defaults["publisher"] = Publisher.objects.get(name=group_param_tuple[0])
    if cls in (Series, Volume):
        defaults["imprint"] = Imprint.objects.get(
            publisher=defaults["publisher"],
            name=group_param_tuple[1],
        )
    if cls is Series:
        defaults["volume_count"] = count
    if cls is Volume:
        defaults["series"] = Series.objects.get(
            publisher=defaults["publisher"],
            imprint=defaults["imprint"],
            name=group_param_tuple[2],
        )
        defaults["issue_count"] = count

    group_obj = cls(**defaults)
    group_obj.presave()
    return group_obj


def _bulk_create_groups(all_create_groups):
    """Create missing groups breadth first."""
    # TODO special code for updating series and volume counts
    if not all_create_groups:
        return False

    num_create_groups = 0
    for cls, group_tree_counts in all_create_groups.items():
        if not group_tree_counts:
            continue
        create_groups = []
        for group_param_tuple, count in group_tree_counts.items():
            obj = _create_group_obj(cls, group_param_tuple, count)
            create_groups.append(obj)
        cls.objects.bulk_create(create_groups)
        num_create_groups = len(create_groups)
        LOG.info(f"Created {num_create_groups} {cls.__name__}s.")
    return num_create_groups > 0


def bulk_folders_modified(library, paths):
    """Update folders stat and nothing else."""
    if not paths:
        return False
    folders = Folder.objects.filter(library=library, path__in=paths).only("stat")
    update_folders = []
    for folder in folders:
        folder.set_stat()
        folder.updated_at = Now()
        update_folders.append(folder)
    Folder.objects.bulk_update(
        update_folders, fields=BULK_UPDATE_FOLDER_MODIFIED_FIELDS
    )
    num_update_folders = len(update_folders)
    LOG.verbose(f"Modified {num_update_folders} folders")  # type: ignore
    return num_update_folders > 0


def bulk_create_folders(library, folder_paths):
    """Create folders breadth first."""
    if not folder_paths:
        return False

    # group folder paths by depth
    folder_path_dict = {}
    for path_str in folder_paths:
        path = Path(path_str)
        path_length = len(path.parts)
        if path_length not in folder_path_dict:
            folder_path_dict[path_length] = []
        folder_path_dict[path_length].append(path)

    # create each depth level first to ensure we can assign parents
    num_create_folders = 0
    for _, paths in sorted(folder_path_dict.items()):
        create_folders = []
        for path in paths:
            name = path.name
            parent_path = str(Path(path).parent)
            if parent_path == library.path:
                parent = None
            else:
                parent = Folder.objects.get(path=parent_path)
            folder = Folder(
                library=library,
                path=str(path),
                name=name,
                parent_folder=parent,
            )
            folder.presave()
            folder.set_stat()
            create_folders.append(folder)
        Folder.objects.bulk_create(create_folders)
        num_create_folders = len(create_folders)
        LOG.info(f"Created {num_create_folders} Folders.")
    return num_create_folders > 0


def _bulk_create_named_models(cls, names):
    """Bulk create named models."""
    if not names:
        return False
    create_named_objs = []
    for name in names:
        named_obj = cls(name=name)
        create_named_objs.append(named_obj)

    cls.objects.bulk_create(create_named_objs)
    num_create_named_objs = len(create_named_objs)
    LOG.info(f"Created {num_create_named_objs} {cls.__name__}s.")
    return num_create_named_objs > 0


def _bulk_create_credits(create_credit_tuples):
    """Bulk create credits."""
    if not create_credit_tuples:
        return False

    create_credits = []
    for role_name, person_name in create_credit_tuples:
        if role_name:
            role = CreditRole.objects.get(name=role_name)
        else:
            role = None
        person = CreditPerson.objects.get(name=person_name)
        credit = Credit(role=role, person=person)

        create_credits.append(credit)

    Credit.objects.bulk_create(create_credits)
    num_create_credits = len(create_credits)
    LOG.info(f"Created {num_create_credits} Credits.")
    return num_create_credits > 0


def bulk_create_all_fks(
    library, create_fks, create_groups, create_paths, create_credits
) -> bool:
    """Bulk create all foreign keys."""
    changed = _bulk_create_groups(create_groups)
    changed |= bulk_create_folders(library, create_paths)
    for cls, names in create_fks.items():
        changed |= _bulk_create_named_models(cls, names)
    # This must happen after credit_fks created by create_named_models
    changed |= _bulk_create_credits(create_credits)
    return changed
