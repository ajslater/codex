"""Repair Database Integrity Errors."""
from logging import getLogger

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db.models import Q
from django.db.models.functions import Now
from django.db.utils import OperationalError


M2M_NAMES = {
    "Character": "characters",
    "Credit": "credits",
    "Genre": "genres",
    "Location": "locations",
    "SeriesGroup": "series_groups",
    "StoryArc": "story_arcs",
    "Tag": "tags",
    "Team": "teams",
    "Folder": "folders",
}
NULL_SET = set([None])
HAVE_LIBRARY_FKS = ("FailedImport", "Folder", "Comic")
GROUP_HOSTS = {
    "Imprint": ("Publisher",),
    "Series": ("Publisher", "Imprint"),
    "Volume": ("Publisher", "Imprint", "Series"),
    "Comic": ("Publisher", "Imprint", "Series", "Volume"),
}
WATCHED_PATHS = ("Comic", "Folder")
CREDIT_FIELDS = {"CreditRole": "role", "CreditPerson": "person"}
LOG = getLogger(__name__)


def _get_invalid_m2m_ids(comic_model, m2m_model, field_name):
    """Query for invalid_m2m_ids."""
    comic_m2m_ids = set(
        comic_model.objects.all().values_list(f"{field_name}__id", flat=True)
    )
    valid_m2m_ids = set(m2m_model.objects.all().values_list("pk", flat=True))
    invalid_m2m_ids = comic_m2m_ids - valid_m2m_ids - set([None])
    num_invalid_m2m_ids = len(invalid_m2m_ids)
    if num_invalid_m2m_ids:
        LOG.verbose(  # type: ignore
            f"Comic.{field_name} - valid: {len(valid_m2m_ids)},"
            f" invalid: {num_invalid_m2m_ids}"
        )
    return invalid_m2m_ids, num_invalid_m2m_ids


def _delete_invalid_m2m_rels(comic_model, m2m_model, field_name, invalid_m2m_ids):
    """Delete the bad m2m relations."""
    field = getattr(comic_model, field_name)
    ThroughModel = field.through  # noqa: N806

    link_name = m2m_model.__name__.lower()
    filter_args = {f"{link_name}_id__in": invalid_m2m_ids}
    query = ThroughModel.objects.filter(**filter_args)
    count = query.count()
    query.delete()
    LOG.info(f"Deleted {count} relations from comics to missing {field_name}.")


def _mark_comics_with_bad_m2m_rels_for_update(comic_model, field_name, invalid_m2m_ids):
    """Mark affected comics for update."""
    bad_comics = comic_model.objects.filter(
        **{f"{field_name}__id__in": invalid_m2m_ids}
    )
    num_bad_comics = bad_comics.count()
    if not num_bad_comics:
        LOG.verbose(f"No Comics with bad {field_name}.")  # type: ignore
        return
    LOG.info(f"Found {num_bad_comics} with bad {field_name}.")

    update_comics = []

    for comic in bad_comics.only("pk", "updated_at"):
        comic.updated_at = 0
        update_comics.append(comic)

    num_update_comics = len(update_comics)
    if not num_update_comics:
        return

    comic_model.objects.bulk_update(update_comics, fields=["updated_at"])
    LOG.info(
        f"Marked {num_update_comics} with missing {field_name} for update by poller."
    )


def _fix_comic_m2m_integrity_errors(apps, m2m_model_name, field_name):
    """Fix Comic ManyToMany integrity errors."""
    comic_model = apps.get_model("codex", "Comic")
    m2m_model = apps.get_model("codex", m2m_model_name)

    invalid_m2m_ids, num_invalid_m2m_ids = _get_invalid_m2m_ids(
        comic_model, m2m_model, field_name
    )
    if not num_invalid_m2m_ids:
        return

    _delete_invalid_m2m_rels(comic_model, m2m_model, field_name, invalid_m2m_ids)

    _mark_comics_with_bad_m2m_rels_for_update(comic_model, field_name, invalid_m2m_ids)


def _find_fk_integrity_errors_with_models(
    host_model, fk_model, fk_field_name, log=True
):
    """Find foreign key integrity errors with specified models."""
    valid_fk_ids = set(fk_model.objects.values_list("pk", flat=True))
    filter = ~Q(**{f"{fk_field_name}__in": valid_fk_ids})
    if (
        host_model.__name__ == "Folder" and fk_field_name == "parent_folder"
    ) or fk_field_name == "role":
        # Special fields can be null
        # THIS IS VERY IMPORTANT TO AVOID DELETING ALL TOP LEVEL FOLDERS
        filter &= Q(**{f"{fk_field_name}__isnull": False})

    invalid_host_objs = host_model.objects.filter(filter)
    count = invalid_host_objs.count()
    if count and log:
        LOG.verbose(  # type: ignore
            f"Found {host_model.__name__}s with bad {fk_field_name}: {count}"
        )
    return invalid_host_objs


def _find_fk_integrity_errors(apps, host_model_name, fk_model_name, fk_field_name):
    """Find foreign key integrity errors."""
    host_model = apps.get_model("codex", host_model_name)
    fk_model = apps.get_model("codex", fk_model_name)
    return _find_fk_integrity_errors_with_models(host_model, fk_model, fk_field_name)


def _delete_query(query, host_model_name, fk_model_name):
    """Execute the delete on the query."""
    num_bad = query.count()
    if num_bad:
        query.delete()
        LOG.info(f"Deleted {num_bad} {host_model_name}s in nonextant {fk_model_name}s.")


def _delete_fk_integrity_errors(apps, host_model_name, fk_model_name, fk_field_name):
    """Delete objects with bad integrity."""
    bad_host_objs = _find_fk_integrity_errors(
        apps, host_model_name, fk_model_name, fk_field_name
    )
    _delete_query(bad_host_objs, host_model_name, fk_model_name)


def _fix_comic_myself_integrity_errors(apps):
    """Fix Comics' self reference."""
    bad_comics = _find_fk_integrity_errors(apps, "Comic", "Comic", "myself")
    update_comics = []
    now = Now()
    for comic in bad_comics.only("myself", "updated_at"):
        comic.myself = comic
        if comic.updated_at:
            # Only if it hasn't been marked for update
            comic.updated_at = now
        update_comics.append(comic)
    num_update_comics = len(update_comics)
    if not num_update_comics:
        return
    comic_model = apps.get_model("codex", "Comic")
    comic_model.objects.bulk_update(update_comics, fields=["myself", "updated_at"])
    LOG.info(f"Repaired {num_update_comics} Comics' self references.")


def _null_missing_fk(host_model, fk_model, fk_field_name):
    """Set missing fks to null."""
    query_missing_fks = _find_fk_integrity_errors_with_models(
        host_model, fk_model, fk_field_name, log=False
    )
    not_null_filter = {f"{fk_field_name}__isnull": False}
    query_missing_fks = query_missing_fks.filter(**not_null_filter)
    count = query_missing_fks.count()
    if count:
        update_dict = {fk_field_name: None, "updated_at": Now()}
        query_missing_fks.only("fk_field_name", "updated_at").update(**update_dict)
        LOG.verbose(  # type: ignore
            f"Fixed {host_model.__name__} with missing {fk_field_name}"
        )


def _delete_userbookmark_integrity_errors(apps):
    """Fix UserBookmarks with non codex model fields."""
    # UserBookmarks that don't refernce a valid comic are useless.
    _delete_fk_integrity_errors(apps, "UserBookmark", "Comic", "comic")

    # UserBookmarks that aren't linked to a valid session or a user are orphans
    ubm_model = apps.get_model("codex", "UserBookmark")
    _null_missing_fk(ubm_model, Session, "session")
    _null_missing_fk(ubm_model, get_user_model(), "user")
    orphan_ubms = ubm_model.objects.filter(session=None, user=None)
    _delete_query(orphan_ubms, "UserBookmark", "session or user")


def _fix_db_integrity():
    """Fix most of the Codex model integrity errors we can."""
    LOG.verbose("Reparing database integrity...")  # type: ignore
    # DELETE things we can't fix
    for host_model_name in HAVE_LIBRARY_FKS:
        _delete_fk_integrity_errors(apps, host_model_name, "Library", "library")

    for host_model_name in WATCHED_PATHS:
        _delete_fk_integrity_errors(apps, host_model_name, "Folder", "parent_folder")

    for host_model_name, groups in GROUP_HOSTS.items():
        for group_model_name in groups:
            group_field_name = group_model_name.lower()
            _delete_fk_integrity_errors(
                apps, host_model_name, group_model_name, group_field_name
            )

    for fk_model_name, fk_field_name in CREDIT_FIELDS.items():
        _delete_fk_integrity_errors(apps, "Credit", fk_model_name, fk_field_name)

    _delete_userbookmark_integrity_errors(apps)

    # REPAIR the objects that are left
    for m2m2_model_name, field_name in M2M_NAMES.items():
        try:
            _fix_comic_m2m_integrity_errors(apps, m2m2_model_name, field_name)
        except OperationalError as exc:
            known_issue = False
            for arg in exc.args:
                if arg == "no such table: codex_comic_folders":
                    LOG.warning(
                        "Couldn't query for comics with folder integrity problems "
                        "before the migrations. We'll get them on the next restart."
                    )
                    known_issue = True
            if not known_issue:
                LOG.exception(exc)

    _fix_comic_myself_integrity_errors(apps)
    LOG.verbose("Done with database integrity check.")  # type: ignore


def repair_db():
    """Fix the db but trap errors if it goes wrong."""
    try:
        _fix_db_integrity()
    except Exception as exc:
        LOG.exception(exc)
