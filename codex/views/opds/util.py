"""OPDS Utility classes."""
from django.db.models import F
from django.utils.http import urlencode

from codex.models import (
    Character,
    Creator,
    CreatorPerson,
    Genre,
    Location,
    SeriesGroup,
    StoryArc,
    Tag,
    Team,
)

OPDS_M2M_MODELS = (Character, Genre, Location, SeriesGroup, StoryArc, Tag, Team)


def update_href_query_params(href, old_query_params, new_query_params=None):
    """Update an href by masking query params on top of the ones it has."""
    query_params = {}
    for key, value in old_query_params.items():
        # qps are sometimes encapsulated in a list for when there's mutiples.
        if isinstance(value, list):
            if len(value):
                query_params[key] = value[0]
        else:
            query_params[key] = value
    if new_query_params:
        query_params.update(new_query_params)
    if query_params:
        href += "?" + urlencode(query_params, doseq=True)
    return href


def get_creator_people(comic_pk, roles, exclude=False):
    """Get creators that are not authors."""
    people = CreatorPerson.objects.filter(
        creator__comic=comic_pk,
    )
    if exclude:
        people = people.exclude(creator__role__name__in=roles)
    else:
        people = people.filter(creator__role__name__in=roles)
    return people.distinct().only("name")


def get_creators(comic_pk, roles, exclude=False):
    """Get credits that are not part of other roles."""
    creators = Creator.objects.filter(comic=comic_pk)
    if exclude:
        creators = creators.exclude(role__name__in=roles)
    else:
        creators = creators.filter(role__name__in=roles)
    return creators.annotate(name=F("person__name"), role_name=F("role__name"))


def get_m2m_objects(pk) -> dict:
    """Get Category labels."""
    cats = {}
    for model in OPDS_M2M_MODELS:
        table = model.__name__.lower()
        qs = model.objects.filter(comic=pk).order_by("name").only("name")
        cats[table] = qs
    return cats
