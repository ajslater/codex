"""Bulk update and create comic objects and bulk update m2m fields."""
from logging import getLogger
from pathlib import Path

from django.db.models import Q

from codex.models import Comic, Credit, Folder, Imprint, Publisher, Series, Volume


LOG = getLogger(__name__)
EXCLUDE_BULK_UPDATE_COMIC_FIELDS = (
    "id",
    "comic",
    "myself",
    "userbookmark",
    "created_at",
    "updated_at",
)
BULK_UPDATE_COMIC_FIELDS = []
for field in Comic._meta.get_fields():
    if not field.many_to_many and field.name not in EXCLUDE_BULK_UPDATE_COMIC_FIELDS:
        BULK_UPDATE_COMIC_FIELDS.append(field.name)


def _get_group_name(cls, md):
    """Get the name of the browse group."""
    field_name = cls.__name__.lower()
    name = md[field_name]
    if name:
        return name
    return cls.DEFAULT_NAME


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
    md["parent_folder"] = Folder.objects.get(path=Path(path).parent)


def _update_comics(library, comic_paths, mds):
    """Bulk update comics."""
    if not comic_paths:
        return

    # Get existing comics to update
    comics = Comic.objects.filter(library=library, path__in=comic_paths).only(
        "pk", *BULK_UPDATE_COMIC_FIELDS
    )

    # set attributes for each comic
    update_comics = []
    for comic in comics:
        md = mds.pop(comic.path)
        _link_comic_fks(md, library, comic.path)
        for field_name, value in md.items():
            setattr(comic, field_name, value)
        comic.presave()
        update_comics.append(comic)

    Comic.objects.bulk_update(update_comics, BULK_UPDATE_COMIC_FIELDS)


def _create_comics(library, comic_paths, mds):
    """Bulk create comics."""
    if not comic_paths:
        return

    # prepare create comics
    create_comics = []
    for path in comic_paths:
        md = mds.pop(path)
        _link_comic_fks(md, library, path)
        comic = Comic(**md)
        comic.presave()
        create_comics.append(comic)

    Comic.objects.bulk_create(create_comics)

    # update myself field with self reference
    created_comics = Comic.objects.filter(path__in=comic_paths).only("pk", "myself")
    for comic in created_comics:
        comic.myself = comic
    Comic.objects.bulk_update(created_comics, ["myself"])


def _link_folders(comic_path):
    """Get the ids of all folders to link."""
    folder_paths = Path(comic_path).parents
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
        cls = Comic._meta.get_field(field).related_model
        if cls is None:
            LOG.error(f"No related class found for Comic.{field}")
            continue
        pks = cls.objects.filter(name__in=names).values_list("pk", flat=True)
        if field not in all_m2m_links:
            all_m2m_links[field] = {}
        all_m2m_links[field][comic_pk] = set(pks)


def _link_comic_m2m_fields(m2m_mds):
    """Get the complete m2m field data to create."""
    all_m2m_links = {}
    comic_paths = set(m2m_mds.keys())

    comics = Comic.objects.filter(path__in=comic_paths).values_list("pk", "path")
    for comic_pk, comic_path in comics:
        md = m2m_mds[comic_path]
        if "folder" not in all_m2m_links:
            all_m2m_links["folder"] = {}
        all_m2m_links["folder"][comic_pk] = _link_folders(comic_path)
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
            tms.append(ThroughModel(**defaults))

    # It is simpler to just nuke and recreate all links than
    #   detect, create & delete them.
    ThroughModel.objects.filter(comic_id__in=m2m_links.keys()).delete()
    ThroughModel.objects.bulk_create(tms)


def bulk_import_comics(library, create_paths, update_paths, all_bulk_mds, all_m2m_mds):
    """Bulk import comics."""
    if not (create_paths or update_paths or all_bulk_mds or all_m2m_mds):
        return

    _update_comics(library, update_paths, all_bulk_mds)
    _create_comics(library, create_paths, all_bulk_mds)
    all_m2m_links = _link_comic_m2m_fields(all_m2m_mds)
    for field_name, m2m_links in all_m2m_links.items():
        bulk_recreate_m2m_field(field_name, m2m_links)
    if update_paths:
        LOG.info(f"Updated {len(update_paths)} Comics.")
    if create_paths:
        LOG.info(f"Created {len(create_paths)} Comics.")
