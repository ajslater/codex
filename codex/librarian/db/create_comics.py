"""Bulk update and create comic objects and bulk update m2m fields."""
from logging import getLogger
from pathlib import Path

from django.db.models import Q
from django.db.models.functions import Now

from codex.librarian.queue_mp import LIBRARIAN_QUEUE, BulkComicCoverCreateTask
from codex.models import (
    Comic,
    Credit,
    FailedImport,
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
)


LOG = getLogger(__name__)
EXCLUDE_BULK_UPDATE_COMIC_FIELDS = (
    "created_at",
    "searchresult",
    "id",
    "userbookmark",
)
BULK_UPDATE_COMIC_FIELDS = []
for field in Comic._meta.get_fields():
    if (not field.many_to_many) and (
        field.name not in EXCLUDE_BULK_UPDATE_COMIC_FIELDS
    ):
        BULK_UPDATE_COMIC_FIELDS.append(field.name)
BULK_UPDATE_FAILED_IMPORT_FIELDS = ("name", "stat", "updated_at")


def _get_group_name(cls, md):
    """Get the name of the browse group."""
    field_name = cls.__name__.lower()
    return md.get(field_name, cls.DEFAULT_NAME)


def _link_comic_fks(md, library, path):
    """Link all foreign keys."""
    publisher_name = _get_group_name(Publisher, md)
    imprint_name = _get_group_name(Imprint, md)
    series_name = _get_group_name(Series, md)
    volume_name = _get_group_name(Volume, md)
    md["library"] = library
    md["publisher"] = Publisher.objects.get(name=publisher_name)
    md["imprint"] = Imprint.objects.get(
        publisher__name=publisher_name, name=imprint_name
    )
    md["series"] = Series.objects.get(
        publisher__name=publisher_name, imprint__name=imprint_name, name=series_name
    )
    md["volume"] = Volume.objects.get(
        publisher__name=publisher_name,
        imprint__name=imprint_name,
        series__name=series_name,
        name=volume_name,
    )
    parent_path = Path(path).parent
    if parent_path == Path(library.path):
        parent_folder = None
    else:
        parent_folder = Folder.objects.get(path=parent_path)
    md["parent_folder"] = parent_folder


def _update_comics(library, comic_paths, mds):
    """Bulk update comics."""
    if not comic_paths:
        return 0

    num_comics = len(comic_paths)
    LOG.verbose(  # type: ignore
        f"Preparing {num_comics} comics for update in library {library.path}."
    )
    # Get existing comics to update
    comics = Comic.objects.filter(library=library, path__in=comic_paths).only(
        "pk", "path", *BULK_UPDATE_COMIC_FIELDS
    )

    # set attributes for each comic
    update_comics = []
    now = Now()
    comic_pks = []
    for comic in comics:
        try:
            md = mds.pop(comic.path)
            _link_comic_fks(md, library, comic.path)
            for field_name, value in md.items():
                setattr(comic, field_name, value)
            comic.presave()
            comic.set_stat()
            comic.updated_at = now  # type: ignore
            update_comics.append(comic)
            comic_pks.append(comic.pk)
        except Exception as exc:
            LOG.error(f"Error preparing {comic} for update.")
            LOG.exception(exc)

    LOG.verbose(f"Bulk updating {num_comics} comics.")  # type: ignore
    count = Comic.objects.bulk_update(update_comics, BULK_UPDATE_COMIC_FIELDS)
    task = BulkComicCoverCreateTask(True, tuple(comic_pks))
    LIBRARIAN_QUEUE.put(task)
    return count


def _create_comics(library, comic_paths, mds):
    """Bulk create comics."""
    if not comic_paths:
        return 0

    num_comics = len(comic_paths)
    LOG.verbose(  # type: ignore
        f"Preparing {num_comics} comics for creation in library {library.path}."
    )
    # prepare create comics
    create_comics = []
    for path in comic_paths:
        try:
            md = mds.pop(path)
            _link_comic_fks(md, library, path)
            comic = Comic(**md)
            comic.presave()
            comic.set_stat()
            create_comics.append(comic)
        except KeyError:
            LOG.warning(f"No comic metadata for {path}")
        except Exception as exc:
            LOG.error(f"Error preparing {path} for create.")
            LOG.exception(exc)

    num_comics = len(create_comics)
    LOG.verbose(f"Bulk creating {num_comics} comics...")  # type: ignore
    created_comics = Comic.objects.bulk_create(create_comics)
    # Start the covers task.
    comic_pks = []
    for comic in created_comics:
        comic_pks.append(comic.pk)
    task = BulkComicCoverCreateTask(True, tuple(comic_pks))
    LIBRARIAN_QUEUE.put(task)
    return num_comics


def _link_folders(folder_paths):
    """Get the ids of all folders to link."""
    if not folder_paths:
        return set()
    folder_pks = Folder.objects.filter(path__in=folder_paths).values_list(
        "pk", flat=True
    )
    return set(folder_pks)


def _link_credits(credits):
    """Get the ids of all credits to link."""
    if not credits:
        return set()
    filter = Q()
    for credit in credits:
        filter_dict = {
            "role__name": credit.get("role"),
            "person__name": credit["person"],
        }
        filter = filter | Q(**filter_dict)
    credit_pks = Credit.objects.filter(filter).values_list("pk", flat=True)
    return set(credit_pks)


def _link_named_m2ms(all_m2m_links, comic_pk, md):
    """Set the ids of all named m2m fields into the comic dict."""
    for field, names in md.items():
        related_model = Comic._meta.get_field(field).related_model
        if related_model is None:
            LOG.error(f"No related class found for Comic.{field}")
            continue
        pks = related_model.objects.filter(name__in=names).values_list("pk", flat=True)
        if field not in all_m2m_links:
            all_m2m_links[field] = {}
        all_m2m_links[field][comic_pk] = set(pks)


def _link_comic_m2m_fields(m2m_mds):
    """Get the complete m2m field data to create."""
    all_m2m_links = {}
    comic_paths = set(m2m_mds.keys())
    LOG.verbose(  # type: ignore
        f"Preparing {len(comic_paths)} comics for many to many relation recreation."
    )

    comics = Comic.objects.filter(path__in=comic_paths).values_list("pk", "path")
    for comic_pk, comic_path in comics:
        md = m2m_mds[comic_path]
        if "folders" not in all_m2m_links:
            all_m2m_links["folders"] = {}
        try:
            folder_paths = md.pop("folders")
        except KeyError:
            folder_paths = []
        all_m2m_links["folders"][comic_pk] = _link_folders(folder_paths)
        if "credits" not in all_m2m_links:
            all_m2m_links["credits"] = {}
        try:
            credits = md.pop("credits")
        except KeyError:
            credits = None
        all_m2m_links["credits"][comic_pk] = _link_credits(credits)
        _link_named_m2ms(all_m2m_links, comic_pk, md)
    return all_m2m_links


def bulk_recreate_m2m_field(field_name, m2m_links):
    """Recreate an m2m field for a set of comics.

    Since we can't bulk_update or bulk_create m2m fields use a trick.
    bulk_create() on the through table:
    https://stackoverflow.com/questions/6996176/how-to-create-an-object-for-a-django-model-with-a-many-to-many-field/10116452#10116452 # noqa: B950,E501
    https://docs.djangoproject.com/en/3.2/ref/models/fields/#django.db.models.ManyToManyField.through # noqa: B950,E501
    """
    LOG.verbose(  # type: ignore
        f"Recreating {field_name} relations for altered comics."
    )
    field = getattr(Comic, field_name)
    ThroughModel = field.through  # noqa: N806
    model = Comic._meta.get_field(field_name).related_model
    if model is None:
        raise ValueError(f"Bad model from {field_name}")
    link_name = model.__name__.lower()
    through_field_id_name = f"{link_name}_id"
    tms = []
    for comic_pk, pks in m2m_links.items():
        for pk in pks:
            defaults = {"comic_id": comic_pk, through_field_id_name: pk}
            tm = ThroughModel(**defaults)
            tms.append(tm)

    # It is simpler to just nuke and recreate all links than
    #   detect, create & delete them.
    ThroughModel.objects.filter(comic_id__in=m2m_links.keys()).delete()
    ThroughModel.objects.bulk_create(tms)
    return len(tms)


def _bulk_update_and_create_failed_imports(library, failed_imports):
    """Bulk update or create failed imports."""
    update_failed_imports = FailedImport.objects.filter(
        library=library, path__in=failed_imports.keys()
    )

    now = Now()
    for fi in update_failed_imports:
        try:
            exc = failed_imports.pop(fi.path)
            fi.set_reason(exc)
            fi.set_stat()
            fi.updated_at = now  # type: ignore
        except Exception as exc:
            LOG.error(f"Error preparing failed import update for {fi.path}")
            LOG.exception(exc)

    create_failed_imports = []
    for path, exc in failed_imports.items():
        try:
            fi = FailedImport(library=library, path=path, parent_folder=None)
            fi.set_reason(exc)
            fi.set_stat()
            create_failed_imports.append(fi)
        except Exception as exc:
            LOG.error(f"Error preparing failed import create for {path}")
            LOG.exception(exc)

    if update_failed_imports:
        update_count = FailedImport.objects.bulk_update(
            update_failed_imports, fields=BULK_UPDATE_FAILED_IMPORT_FIELDS
        )
        if update_count is None:
            update_count = 0
    else:
        update_count = 0
    if create_failed_imports:
        FailedImport.objects.bulk_create(create_failed_imports)
    create_count = len(create_failed_imports)
    log = f"Failed {create_count} new, {update_count} old comic imports."
    total_count = update_count + create_count
    if total_count:
        LOG.warning(log)
    else:
        LOG.verbose(log)  # type: ignore


def bulk_import_comics(
    library, create_paths, update_paths, all_bulk_mds, all_m2m_mds, failed_imports
):
    """Bulk import comics."""
    update_paths -= failed_imports.keys()
    create_paths -= failed_imports.keys()

    if not (
        create_paths or update_paths or all_bulk_mds or all_m2m_mds or failed_imports
    ):
        return 0

    update_count = _update_comics(library, update_paths, all_bulk_mds)
    create_count = _create_comics(library, create_paths, all_bulk_mds)

    all_m2m_links = _link_comic_m2m_fields(all_m2m_mds)
    for field_name, m2m_links in all_m2m_links.items():
        try:
            bulk_recreate_m2m_field(field_name, m2m_links)
        except Exception as exc:
            LOG.error(f"Error recreating m2m field: {field_name}")
            LOG.exception(exc)

    update_log = f"Updated {update_count} Comics."
    if update_count:
        LOG.info(update_log)
    else:
        LOG.verbose(update_log)  # type: ignore
    create_log = f"Created {create_count} Comics."
    if create_count:
        LOG.info(create_log)
    else:
        LOG.verbose(create_log)  # type: ignore

    _bulk_update_and_create_failed_imports(library, failed_imports)

    total_count = update_count + create_count
    return total_count
