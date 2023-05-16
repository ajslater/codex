"""OPDS Utility classes."""
from django.db.models import F
from django.http.response import HttpResponseRedirect
from django.urls import reverse
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
from codex.serializers.choices import DEFAULTS

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


def full_redirect_view(url_name):
    """Redirect to view, for a url name."""

    def func(request):
        """Redirect to view, forwarding query strings and auth."""
        kwargs = DEFAULTS["route"]
        url = reverse(url_name, kwargs=kwargs)

        # Forward the query string.
        path = request.get_full_path()
        if path:
            parts = path.split("?")
            if len(parts) >= 2:  # noqa PLR2004
                parts[0] = url
                url = "?".join(parts)

        response = HttpResponseRedirect(url)

        # Forward authorization.
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header:
            response["HTTP_AUTHORIZATION"] = auth_header

        return response

    return func
