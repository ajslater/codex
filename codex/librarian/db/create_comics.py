"""Bulk update and create comic objects and bulk update m2m fields."""
from pathlib import Path

from django.db.models import Q
from django.db.models.functions import Now

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.db.status import ImportStatusTypes
from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.status_control import StatusControl
from codex.models import (
    Comic,
    Credit,
    Folder,
    Imprint,
    Publisher,
    Series,
    Timestamp,
    Volume,
)
from codex.settings.logging import get_logger


LOG = get_logger(__name__)
EXCLUDE_BULK_UPDATE_COMIC_FIELDS = (
    "created_at",
    "searchresult",
    "id",
    "bookmark",
)
BULK_UPDATE_COMIC_FIELDS = []
for field in Comic._meta.get_fields():
    if (not field.many_to_many) and (
        field.name not in EXCLUDE_BULK_UPDATE_COMIC_FIELDS
    ):
        BULK_UPDATE_COMIC_FIELDS.append(field.name)


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
    md["parent_folder"] = Folder.objects.get(path=parent_path)


def _update_comics(library, comic_paths, mds):
    """Bulk update comics."""
    if not comic_paths:
        return 0

    num_comics = len(comic_paths)
    LOG.verbose(f"Preparing {num_comics} comics for update in library {library.path}.")
    # Get existing comics to update
    comics = Comic.objects.filter(library=library, path__in=comic_paths).only(
        *BULK_UPDATE_COMIC_FIELDS
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
            comic.updated_at = now
            update_comics.append(comic)
            comic_pks.append(comic.pk)
        except Exception as exc:
            LOG.error(f"Error preparing {comic} for update.")
            LOG.exception(exc)

    LOG.verbose(f"Bulk updating {num_comics} comics.")
    count = Comic.objects.bulk_update(update_comics, BULK_UPDATE_COMIC_FIELDS)
    task = CoverRemoveTask(frozenset(comic_pks))
    LOG.verbose(f"Purging covers for {len(comic_pks)} updated comics.")
    LIBRARIAN_QUEUE.put(task)
    return count


def _create_comics(library, comic_paths, mds):
    """Bulk create comics."""
    if not comic_paths:
        return 0

    num_comics = len(comic_paths)
    LOG.verbose(
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
    LOG.verbose(f"Bulk creating {num_comics} comics...")
    created_comics = Comic.objects.bulk_create(create_comics)
    return len(created_comics)


def _link_folders(folder_paths):
    """Get the ids of all folders to link."""
    if not folder_paths:
        return set()
    folder_pks = Folder.objects.filter(path__in=folder_paths).values_list(
        "pk", flat=True
    )
    return frozenset(folder_pks)


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
    return frozenset(credit_pks)


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
        all_m2m_links[field][comic_pk] = frozenset(pks)


def _link_comic_m2m_fields(m2m_mds):
    """Get the complete m2m field data to create."""
    all_m2m_links = {}
    comic_paths = frozenset(m2m_mds.keys())
    LOG.verbose(
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
    https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.ManyToManyField.through # noqa: B950,E501
    """
    LOG.verbose(f"Recreating {field_name} relations for altered comics.")
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


def bulk_import_comics(library, create_paths, update_paths, all_bulk_mds, all_m2m_mds):
    """Bulk import comics."""
    if not (create_paths or update_paths or all_bulk_mds or all_m2m_mds):
        StatusControl.finish_many(
            (
                ImportStatusTypes.FILES_MODIFIED,
                ImportStatusTypes.FILES_CREATED,
                ImportStatusTypes.LINK_M2M_FIELDS,
            )
        )
        return 0

    update_count = create_count = 0
    try:
        try:
            try:
                StatusControl.start(
                    ImportStatusTypes.FILES_MODIFIED, name=f"({len(update_paths)})"
                )
                update_count = _update_comics(library, update_paths, all_bulk_mds)
            finally:
                StatusControl.finish(ImportStatusTypes.FILES_MODIFIED)
            StatusControl.start(
                ImportStatusTypes.FILES_CREATED, name=f"({len(create_paths)})"
            )
            create_count = _create_comics(library, create_paths, all_bulk_mds)
        finally:
            StatusControl.finish(ImportStatusTypes.FILES_CREATED)
            # Just to be sure.
        all_m2m_links = _link_comic_m2m_fields(all_m2m_mds)
        total_links = 0
        for m2m_links in all_m2m_links.values():
            total_links += len(m2m_links)
        StatusControl.start(ImportStatusTypes.LINK_M2M_FIELDS, total_links)

        for m2m_links in all_m2m_links.values():
            completed_links = 0
            for field_name, m2m_links in all_m2m_links.items():
                try:
                    bulk_recreate_m2m_field(field_name, m2m_links)
                except Exception as exc:
                    LOG.error(f"Error recreating m2m field: {field_name}")
                    LOG.exception(exc)
                completed_links = len(m2m_links)
                StatusControl.update(
                    ImportStatusTypes.LINK_M2M_FIELDS, completed_links, total_links
                )
    finally:
        StatusControl.finish(ImportStatusTypes.LINK_M2M_FIELDS)

    if update_count is None:
        update_count = 0
    if create_count is None:
        create_count = 0

    update_log = f"Updated {update_count} Comics."
    if update_count:
        Timestamp.touch(Timestamp.COVERS)
        LOG.info(update_log)
    else:
        LOG.verbose(update_log)
    create_log = f"Created {create_count} Comics."
    if create_count:
        LOG.info(create_log)
    else:
        LOG.verbose(create_log)

    total_count = update_count + create_count
    return total_count
