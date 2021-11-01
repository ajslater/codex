"""Query the missing foreign keys for comics and credits."""
from pathlib import Path

from django.db.models import Q

from codex.librarian.bulk_import import BROWSER_GROUPS
from codex.models import Comic, Credit, Folder, Imprint, Publisher, Series, Volume


CREDIT_FKS = ("role", "person")

CREDIT_QUERY_FIELDS = ("role__name", "person__name")
FOLDER_QUERY_FIELDS = ("path",)
QUERY_FIELDS = {
    Credit: ("role__name", "person__name"),
    Folder: ("path",),
    Imprint: ("publisher__name", "name"),
    Series: ("publisher__name", "imprint__name", "name"),
    Volume: ("publisher__name", "imprint__name", "series__name", "name"),
}
NAMED_MODEL_QUERY_FIELDS = ("name",)
# sqlite parser breaks with more than 1000 lines in a query and django only fixes this
# in the bulk_create & bulk_update functions. So for complicated queries I gotta batch
# them myself
# Filter arg count is a poor proxy for sql line length but it works
#   1998 is too high for the Credit query, for instance.
FILTER_ARG_MAX = 1950


def _get_create_metadata(fk_cls, create_mds, filter_batches):
    """Get create metadata by comparing proposed meatada to existing rows."""
    # XXX filter could be too long with thousands of credits or paths for the filter?
    fields = QUERY_FIELDS.get(fk_cls, NAMED_MODEL_QUERY_FIELDS)
    flat = len(fields) == 1 and fk_cls != Publisher
    # Do this in batches so as not to exceed the 1k line sqlite limit
    for filter in filter_batches:
        existing_mds = set(
            fk_cls.objects.filter(filter).order_by("pk").values_list(*fields, flat=flat)
        )
        create_mds -= existing_mds

    return create_mds


def _add_parent_group_filter(group_name, field_name, cls, filter_args):
    """Get the parent group filter by name."""
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


def _query_missing_group_type(cls, groups):
    """Get missing groups from proposed groups to create."""

    # create the filters
    filter = Q()
    candidates = {}
    filter_batches = []
    filter_arg_count = 0
    for group_tree, count in groups.items():
        filter_args = {}
        _add_parent_group_filter(group_tree[-1], "", cls, filter_args)
        if cls in (Imprint, Series, Volume):
            _add_parent_group_filter(group_tree[0], "publisher", Publisher, filter_args)
        if cls in (Series, Volume):
            _add_parent_group_filter(group_tree[1], "imprint", Imprint, filter_args)
        if cls == Volume:
            _add_parent_group_filter(group_tree[2], "series", Series, filter_args)

        num_filter_args = len(filter_args)
        if filter_arg_count + num_filter_args > FILTER_ARG_MAX:
            filter_batches.append(filter)
            filter = Q()
            filter_arg_count = 0

        filter = filter | Q(**filter_args)
        filter_arg_count += num_filter_args

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
    if filter != Q():
        filter_batches.append(filter)

    # get the create metadata
    create_group_set = _get_create_metadata(cls, set(candidates.keys()), filter_batches)

    # Append the count metadata to the create_groups
    create_groups = {}
    for group, count_dict in candidates.items():
        if group in create_group_set:
            create_groups[group] = count_dict
    return create_groups


def _query_missing_groups(group_trees_md):
    """Get missing groups from proposed groups to create."""
    # XXX Missing a facility to update Series & Volume count fields on already
    #     created groups

    all_create_groups = {}
    for cls, groups in group_trees_md.items():
        create_groups = _query_missing_group_type(cls, groups)
        all_create_groups[cls] = create_groups
    return all_create_groups


def _query_missing_credits(credits):
    """Find missing credit objects."""

    # create the filter
    filter = Q()
    comparison_credits = set()
    filter_batches = []
    filter_arg_count = 0
    for credit_tuple in credits:
        credit_dict = dict(credit_tuple)
        role = credit_dict.get("role")
        person = credit_dict["person"]
        filter_args = {
            "person__name": person,
            "role__name": role,
        }

        if filter_arg_count + 2 > FILTER_ARG_MAX:
            filter_batches.append(filter)
            filter = Q()
            filter_arg_count = 0

        filter = filter | Q(**filter_args)
        filter_arg_count += 2

        comparison_tuple = (role, person)
        comparison_credits.add(comparison_tuple)
    if filter != Q():
        filter_batches.append(filter)

    # get the create metadata
    create_credits = _get_create_metadata(Credit, comparison_credits, filter_batches)

    return create_credits


def _query_missing_named_models(cls, field, names):
    """Find missing named models."""
    fk_cls = cls._meta.get_field(field).related_model

    filter_batches = []
    offset = 0
    proposed_names = list(names)
    num_proposed_names = len(proposed_names)
    while offset < num_proposed_names:
        end = offset + FILTER_ARG_MAX
        filter = Q(name__in=proposed_names[offset:end])
        filter_batches.append(filter)
        offset += FILTER_ARG_MAX

    create_names = _get_create_metadata(fk_cls, names, filter_batches)
    return fk_cls, create_names


def query_missing_folder_paths(library_path, comic_paths):
    """Find missing folder paths."""

    # create the filter
    folder_paths = set()

    library_path = Path(library_path)
    for comic_path in comic_paths:
        for path in Path(comic_path).parents:
            if path.is_relative_to(library_path) and path != library_path:
                folder_paths.add(str(path))

    proposed_folder_paths = list(folder_paths)
    num_proposed_folder_paths = len(proposed_folder_paths)

    filter_batches = []
    offset = 0
    while offset < num_proposed_folder_paths:
        end = offset + FILTER_ARG_MAX
        filter = Q(path__in=proposed_folder_paths[offset:end])
        filter_batches.append(filter)
        offset += FILTER_ARG_MAX

    # get the create metadata
    create_folder_paths = _get_create_metadata(Folder, folder_paths, filter_batches)
    return create_folder_paths


def query_all_missing_fks(library_path, fks):
    """Get objects to create by querying existing objects for the proposed fks."""
    create_credits = set()
    if "credits" in fks:
        credits = fks.pop("credits")
        create_credits |= _query_missing_credits(credits)

    create_groups = {}
    if "group_trees" in fks:
        group_trees = fks.pop("group_trees")
        create_groups.update(_query_missing_groups(group_trees))

    create_paths = set()
    if "comic_paths" in fks:
        create_paths |= query_missing_folder_paths(library_path, fks.pop("comic_paths"))

    create_fks = {}
    for field in fks.keys():
        names = fks.get(field)
        if field in CREDIT_FKS:
            base_cls = Credit
        else:
            base_cls = Comic
        cls, names = _query_missing_named_models(base_cls, field, names)
        create_fks[cls] = names

    return create_fks, create_groups, create_paths, create_credits
