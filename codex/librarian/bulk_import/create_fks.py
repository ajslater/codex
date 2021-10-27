""""
Create all missing comic foreign keys for an import.
So we may safely create the comics next.
"""

from pathlib import Path

from codex.librarian.bulk_import.query_fks import query_all_missing_fks
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


def _create_group_obj(cls, group_param_tuple, count):
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
    if defaults["name"] == cls.DEFAULT_NAME:
        defaults["is_default"] = True
    return cls(**defaults)


def _create_missing_groups(all_create_groups):
    """Create missing groups breadth first."""
    # TODO special code for updating series and volume counts
    if not all_create_groups:
        return

    for cls, group_tree_counts in all_create_groups.items():
        if not group_tree_counts:
            continue
        create_groups = []
        for group_param_tuple, count in group_tree_counts.items():
            obj = _create_group_obj(cls, group_param_tuple, count)
            create_groups.append(obj)
        cls.objects.bulk_create(create_groups)


def create_missing_folders(library, folder_paths):
    """Create folders breadth first."""
    # group folder paths by depth
    folder_path_dict = {}
    for path_str in folder_paths:
        path = Path(path_str)
        path_length = len(path.parts)
        if path_length not in folder_path_dict:
            folder_path_dict[path_length] = []
        folder_path_dict[path_length].append(path)

    # create each depth level first to ensure we can assign parents
    for _, paths in sorted(folder_path_dict.items()):
        folders = []
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
                sort_name=name,
                parent_folder=parent,
            )
            folders.append(folder)
        Folder.objects.bulk_create(folders)


def _create_missing_named_models(cls, names):
    if not names:
        return
    named_objs = []
    for name in names:
        named_obj = cls(name=name)
        named_objs.append(named_obj)

    cls.objects.bulk_create(named_objs)


def _create_missing_credits(create_credit_tuples):
    if not create_credit_tuples:
        return

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


def _create_all_missing_fks(
    library, create_fks, create_groups, create_paths, create_credits
):

    _create_missing_groups(create_groups)

    create_missing_folders(library, create_paths)

    # XXX credit_fk_keys = set(create_fks.keys()) & set([CreditRole, CreditPerson])
    for cls, names in create_fks.items():
        _create_missing_named_models(cls, names)

    _create_missing_credits(create_credits)


def bulk_create_comic_relations(library, fks):

    create_fks, create_groups, create_paths, create_credits = query_all_missing_fks(
        library.path, fks
    )

    _create_all_missing_fks(
        library, create_fks, create_groups, create_paths, create_credits
    )
