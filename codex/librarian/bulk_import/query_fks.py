"""Query the missing foreign keys for comics and credits."""
from pathlib import Path

from django.db.models import Q

from codex.librarian.bulk_import import BROWSER_GROUPS
from codex.models import Comic, Credit, Folder, Imprint, Publisher, Series, Volume


CREDIT_FKS = ("role", "person")


def add_group_key(group_name, field_name, cls, filter_args):
    if field_name:
        key = f"{field_name}__"
    else:
        key = ""

    if group_name:
        key += "name"
        val = group_name
    else:
        # key += "is_default"
        # val = True
        key += "name"
        val = cls.DEFAULT_NAME
    filter_args[key] = val


def query_missing_group_type(cls, groups):

    filter = Q()
    candidates = {}
    for group_tree, count in groups.items():
        filter_args = {}
        add_group_key(group_tree[-1], "", cls, filter_args)
        if cls in (Imprint, Series, Volume):
            add_group_key(group_tree[0], "publisher", Publisher, filter_args)
        if cls in (Series, Volume):
            add_group_key(group_tree[1], "imprint", Imprint, filter_args)
        if cls == Volume:
            add_group_key(group_tree[2], "series", Series, filter_args)

        filter = filter | Q(**filter_args)

        # XXX ugly hack for DEFAULT_NAME issue in data model
        #  DEFAULT_NAME in general is a bad hack. DB name should be None or empty str
        #  for these and adjusted for display.
        candidate_tree = []
        for group, group_cls in zip(group_tree, BROWSER_GROUPS):
            if group:
                candidate_tree.append(group)
            else:
                candidate_tree.append(group_cls.DEFAULT_NAME)
        candidates[tuple(candidate_tree)] = count

    values_list = []  # The order of this is important for set comparisons afterwards
    if cls in (Imprint, Series, Volume):
        values_list += ["publisher__name"]
    if cls in (Series, Volume):
        values_list += ["imprint__name"]
    if cls == Volume:
        values_list += ["series__name"]
    values_list += ["name"]

    candidates_set = set(candidates.keys())
    existing_groups = set(cls.objects.filter(filter).values_list(*values_list))
    create_group_set = candidates_set - existing_groups

    create_groups = {}
    for group, count_dict in candidates.items():
        if group in create_group_set:
            create_groups[group] = count_dict
    return create_groups


def none_max(a, b):
    if a is not None and b is not None:
        return max(a, b)
    if a is None:
        return b
    if b is None:
        return a


def query_missing_groups(group_trees_md):
    # XXX Missing a facility to update Series & Volume count fields on already
    #     created groups

    # TODO move this loop into aggregate and modularize!!!
    all_groups = {Publisher: {}, Imprint: {}, Series: {}, Volume: {}}
    for group_tree, group_md in group_trees_md.items():
        all_groups[Publisher][group_tree[0:1]] = None
        all_groups[Imprint][group_tree[0:2]] = None

        series_group_tree = group_tree[0:3]
        volume_count = none_max(
            all_groups[Series].get(series_group_tree), group_md.get("volume_count")
        )
        all_groups[Series][series_group_tree] = volume_count
        volume_group_tree = group_tree[0:4]
        issue_count = none_max(
            all_groups[Volume].get(volume_group_tree), group_md.get("issue_count")
        )
        all_groups[Volume][volume_group_tree] = issue_count

    all_create_groups = {}
    for cls, groups in all_groups.items():
        create_groups = query_missing_group_type(cls, groups)
        all_create_groups[cls] = create_groups
    return all_create_groups


def query_missing_paths(library_path, comic_paths):
    folder_paths = set()

    library_path = Path(library_path)
    for comic_path in comic_paths:
        for path in Path(comic_path).parents:
            if path.is_relative_to(library_path) and path != library_path:
                folder_paths.add(str(path))

    existing_folder_paths = Folder.objects.filter(path__in=folder_paths).values_list(
        "path", flat=True
    )
    create_folder_paths = folder_paths - set(existing_folder_paths)
    return create_folder_paths


def query_missing_credits(credits):
    filter = Q()
    comparison_credits = set()
    for credit_tuple in credits:
        credit_dict = dict(credit_tuple)
        role = credit_dict.get("role")
        person = credit_dict["person"]
        filter_args = {
            "person__name": person,
            "role__name": role,
        }
        filter = filter | Q(**filter_args)
        comparison_tuple = (role, person)
        comparison_credits.add(comparison_tuple)

    existing_credits = Credit.objects.filter(filter).values_list(
        "role__name", "person__name"
    )
    create_credits = comparison_credits - set(existing_credits)
    return create_credits


def query_missing_named_models(cls, field, names):
    fk_cls = cls._meta.get_field(field).related_model
    existing_names = set(
        fk_cls.objects.filter(name__in=names).values_list("name", flat=True)
    )
    create_names = names - existing_names
    return fk_cls, create_names


def query_all_missing_fks(library_path, fks):

    create_credits = set()
    if "credits" in fks:
        credits = fks.pop("credits")
        create_credits |= query_missing_credits(credits)

    create_groups = {}
    if "group_trees" in fks:
        group_trees = fks.pop("group_trees")
        create_groups.update(query_missing_groups(group_trees))

    create_paths = set()
    if "comic_paths" in fks:
        create_paths |= query_missing_paths(library_path, fks.pop("comic_paths"))

    create_fks = {}
    for field in fks.keys():
        names = fks.get(field)
        if field in CREDIT_FKS:
            base_cls = Credit
        else:
            base_cls = Comic
        cls, names = query_missing_named_models(base_cls, field, names)
        create_fks[cls] = names

    return create_fks, create_groups, create_paths, create_credits
