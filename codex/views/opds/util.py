"""OPDS Utility classes."""

from collections.abc import Callable, Iterable, Sequence

from django.db.models import F
from django.http.response import HttpResponseRedirect
from django.urls import reverse
from rest_framework.request import Request

from codex.choices.browser import DEFAULT_BROWSER_ROUTE
from codex.models import (
    Credit,
    CreditPerson,
)
from codex.views.auth import GroupACLMixin
from codex.views.opds.const import OPDS_M2M_MODELS

#################
# M2M QuerySets #
#################
# These M2M queries could techinally be added to the main query, but
# probably only if the desired output format was already known. Like a
# json object of model_name-pk, name for opds v1 and a json list of
# strings for opds v2. Its actually better from a code standpoint to
# not optimize the query like that, I think, and send the several
# querysets to the views and templates.


def get_credit_people(comic_pks: Sequence[int], roles: Iterable[str], *, exclude: bool):
    """Get credits that are not authors."""
    people = CreditPerson.objects.filter(
        credit__comic__in=comic_pks,
    )
    if exclude:
        people = people.exclude(credit__role__name__in=roles)
    else:
        people = people.filter(credit__role__name__in=roles)
    return people.distinct().only("name")


def get_credits(comic_pks: Sequence[int], roles: Iterable[str], *, exclude: bool):
    """Get credits that are not part of other roles."""
    credit_qs = Credit.objects.filter(comic__in=comic_pks)
    if exclude:
        credit_qs = credit_qs.exclude(role__name__in=roles)
    else:
        credit_qs = credit_qs.filter(role__name__in=roles)
    return credit_qs.annotate(name=F("person__name"), role_name=F("role__name"))


def get_m2m_objects(pks: Sequence[int]) -> dict:
    """Get Category labels."""
    cats = {}
    for model in OPDS_M2M_MODELS:
        table = model.__name__.lower()
        rel = GroupACLMixin.get_rel_prefix(model)
        comic_filter = {rel + "in": pks}
        qs = model.objects.filter(**comic_filter).only("name").order_by("name")
        cats[table] = qs

    return cats


###################
# Other Utilities #
###################


def full_redirect_view(url_name: str) -> Callable[[Request], HttpResponseRedirect]:
    """Redirect to view, for a url name."""

    def func(request: Request):
        """Redirect to view, forwarding query strings and auth."""
        kwargs = dict(DEFAULT_BROWSER_ROUTE)
        url = reverse(url_name, kwargs=kwargs, query=request.GET)
        response = HttpResponseRedirect(url)

        # Forward authorization.
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header:
            response["HTTP_AUTHORIZATION"] = auth_header

        return response

    return func


def get_user_agent_name(request: Request) -> str:
    """Parse User Agent Name from Request."""
    if (user_agent := request.headers.get("User-Agent")) and (
        user_agent_parts := user_agent.split("/", 1)
    ):
        user_agent_name = user_agent_parts[0]
    else:
        user_agent_name = ""
    return user_agent_name
