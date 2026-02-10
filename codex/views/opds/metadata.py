"""OPDS Metadata Subqueries."""

from collections.abc import Iterable, Sequence

from django.db.models import F

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
