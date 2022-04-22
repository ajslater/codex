"""
Create all missing comic foreign keys for an import.

So we may safely create the comics next.
"""

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
from codex.settings.logging import get_logger


BULK_UPDATE_FOLDER_MODIFIED_FIELDS = ("stat", "updated_at")
COUNT_FIELDS = {Series: "volume_count", Volume: "issue_count"}
LOG = get_logger(__name__)


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
    elif cls is Volume:
        defaults["series"] = Series.objects.get(
            publisher=defaults["publisher"],
            imprint=defaults["imprint"],
            name=group_param_tuple[2],
        )
        defaults["issue_count"] = count

    group_obj = cls(**defaults)
    return group_obj


def _update_group_obj(cls, group_param_tuple, count, count_field):
    """Update group counts for a Series or Volume."""
    if count is None:
        return None
    search_kwargs = {
        "publisher__name": group_param_tuple[0],
        "imprint__name": group_param_tuple[1],
        "name": group_param_tuple[-1],
    }
    if cls == Volume:
        search_kwargs["series__name"] = group_param_tuple[2]

    obj = cls.objects.get(**search_kwargs)
    obj_count = getattr(obj, count_field)
    if obj_count is None or obj_count < count:
        setattr(obj, count_field, count)
    else:
        obj = None
    return obj


def _bulk_group_creator(group_tree_counts, cls):
    """Bulk creates groups."""
    create_groups = []
    for group_param_tuple, count in group_tree_counts.items():
        obj = _create_group_obj(cls, group_param_tuple, count)
        create_groups.append(obj)
    cls.objects.bulk_create(create_groups)
    return len(create_groups)


def _bulk_group_updater(group_tree_counts, cls):
    """Bulk update groups."""
    update_groups = []
    count_field = COUNT_FIELDS[cls]
    for group_param_tuple, count in group_tree_counts.items():
        obj = _update_group_obj(cls, group_param_tuple, count, count_field)
        if obj:
            update_groups.append(obj)
    return cls.objects.bulk_update(update_groups, fields=[count_field])


def _bulk_create_or_update_groups(all_operation_groups, func, log_tion, log_verb):
    """Create missing groups breadth first."""
    if not all_operation_groups:
        return False

    num_operation_groups = 0
    for cls, group_tree_counts in all_operation_groups.items():
        if not group_tree_counts:
            continue
        LOG.verbose(
            f"Preparing {len(group_tree_counts)} {cls.__name__}s for {log_tion}..."
        )
        count = func(group_tree_counts, cls)

        num_operation_groups += count
        log = f"{log_verb} {count} {cls.__name__}s."
        if count:
            LOG.info(log)
        else:
            LOG.verbose(log)

    return num_operation_groups > 0


def bulk_folders_modified(library, paths):
    """Update folders stat and nothing else."""
    if not paths:
        return False
    LOG.verbose(f"Preparing {len(paths)} folders for modification...")
    folders = Folder.objects.filter(library=library, path__in=paths).only(
        "stat", "updated_at"
    )
    update_folders = []
    now = Now()
    for folder in folders:
        if Path(folder.path).exists():
            folder.set_stat()
            folder.updated_at = now
            update_folders.append(folder)
    count = Folder.objects.bulk_update(
        update_folders, fields=BULK_UPDATE_FOLDER_MODIFIED_FIELDS
    )
    log = f"Modified {count} folders"
    if count:
        LOG.info(log)
    else:
        LOG.verbose(log)

    return bool(count)


def bulk_folders_create(library, folder_paths):
    """Create folders breadth first."""
    if not folder_paths:
        return False

    num_folder_paths = len(folder_paths)
    LOG.verbose(f"Preparing {num_folder_paths} folders for creation.")
    # group folder paths by depth
    folder_path_dict = {}
    for path_str in folder_paths:
        path = Path(path_str)
        path_length = len(path.parts)
        if path_length not in folder_path_dict:
            folder_path_dict[path_length] = set()
        folder_path_dict[path_length].add(path)

    # create each depth level first to ensure we can assign parents
    total_count = 0
    for _, paths in sorted(folder_path_dict.items()):
        create_folders = []
        for path in sorted(paths):
            parent_path = str(path.parent)
            parent = None
            try:
                parent = Folder.objects.get(path=parent_path)
            except Folder.DoesNotExist:
                if parent_path != library.path:
                    LOG.error(f"Can't find parent folder {parent_path} for {path}")
            folder = Folder(
                library=library,
                path=str(path),
                name=path.name,
                parent_folder=parent,
            )
            folder.set_stat()
            create_folders.append(folder)
        Folder.objects.bulk_create(create_folders)
        count = len(create_folders)
        total_count += count
        log = f"Created {total_count}/{num_folder_paths} Folders."
        if count:
            LOG.info(log)
        else:
            LOG.verbose(log)
    return total_count > 0


def _bulk_create_named_models(cls, names):
    """Bulk create named models."""
    if not names:
        return False
    count = len(names)
    LOG.verbose(f"Preparing {count} {cls.__name__}s for creation...")
    create_named_objs = []
    for name in names:
        named_obj = cls(name=name)
        create_named_objs.append(named_obj)

    cls.objects.bulk_create(create_named_objs)
    log = f"Created {count} {cls.__name__}s."
    if count:
        LOG.info(log)
    else:
        LOG.verbose(log)
    return count > 0


def _bulk_create_credits(create_credit_tuples):
    """Bulk create credits."""
    if not create_credit_tuples:
        return False

    LOG.verbose(f"Preparing {len(create_credit_tuples)} credits for creation...")
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
    count = len(create_credits)
    log = f"Created {count} Credits."
    if count:
        LOG.info(log)
    else:
        LOG.verbose(log)

    return count > 0


def bulk_create_all_fks(
    library,
    create_fks,
    create_groups,
    update_groups,
    create_folder_paths,
    create_credits,
) -> bool:
    """Bulk create all foreign keys."""
    LOG.verbose(f"Creating comic foreign keys for {library.path}...")
    changed = _bulk_create_or_update_groups(
        create_groups, _bulk_group_creator, "creation", "Created"
    )
    changed |= _bulk_create_or_update_groups(
        update_groups, _bulk_group_updater, "update", "Updated"
    )

    changed |= bulk_folders_create(library, create_folder_paths)
    for cls, names in create_fks.items():
        changed |= _bulk_create_named_models(cls, names)
    # This must happen after credit_fks created by create_named_models
    changed |= _bulk_create_credits(create_credits)
    return changed
