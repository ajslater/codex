"""View for marking comics read and unread."""
import logging
import time

from django.db.models import FilteredRelation
from django.http import FileResponse
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.models import Comic
from codex.serializers.metadata import MetadataSerializer
from codex.serializers.metadata import UserBookmarkFinishedSerializer
from codex.settings import DEBUG
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browse_metadata_base import BrowseMetadataBase
from codex.views.mixins import SessionMixin
from codex.views.mixins import UserBookmarkMixin


LOG = logging.getLogger(__name__)


class ComicDownloadView(APIView):
    """Return the comic archive file as an attachment."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def get(self, request, *args, **kwargs):
        """Download a comic archive."""
        pk = kwargs.get("pk")
        try:
            comic_path = Comic.objects.only("path").get(pk=pk).path
        except Comic.DoesNotExist:
            raise Http404(f"Comic {pk} not not found.")

        fd = open(comic_path, "rb")
        return FileResponse(fd, as_attachment=True)


class UserBookmarkFinishedView(APIView, SessionMixin, UserBookmarkMixin):
    """Mark read or unread recursively."""

    # TODO possibly combine with ComicBookmarkView

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    def patch(self, request, *args, **kwargs):
        """Mark read or unread recursively."""
        serializer = UserBookmarkFinishedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = self.kwargs.get("group")
        relation = BrowseMetadataBase.GROUP_RELATION.get(group)
        pk = self.kwargs.get("pk")
        # Optimizing this call with only seems to fail the subsequent updates
        comics = Comic.objects.filter(**{relation: pk})
        updates = {"finished": serializer.validated_data.get("finished")}

        for comic in comics:
            # can't do this in bulk if using update_or_create withtout a
            # third party packages.
            self.update_user_bookmark(updates, comic=comic)

        return Response()


class MetadataView(BrowseMetadataBase, SessionMixin, UserBookmarkMixin):
    """Comic metadata."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    CONTAINER_AGG_SERIALIZER_MAP = {
        "bookmark": "bookmark",
        "child_count": "childCount",
        "x_cover_path": "coverPath",
        "finished": "finished",
        "progress": "progress",
        "size": "size",
        "x_page_count": "pageCount",
    }
    CONTAINER_VALUES = tuple(
        list(CONTAINER_AGG_SERIALIZER_MAP.keys()) + ["x_comic__pk"]
    )
    COMIC_FK_SERIALIZER_MAP = {
        "imprint": "imprintChoices",
        "publisher": "publisherChoices",
        "series": "seriesChoices",
        "volume": "volumeChoices",
    }
    COMIC_M2M_SERIALIZER_MAP = {
        "characters": "charactersChoices",
        "genres": "genresChoices",
        "locations": "locationsChoices",
        "series_groups": "seriesGroupsChoices",
        "story_arcs": "storyArcsChoices",
        "tags": "tagsChoices",
        "teams": "teamsChoices",
    }
    # TODO do vue choice transforms on the client side
    VUE_CHOICE_KEYS = tuple(
        list(COMIC_FK_SERIALIZER_MAP.values()) + list(COMIC_M2M_SERIALIZER_MAP.values())
    )

    COMIC_FIELD_SERIALIZER_MAP = {
        "country": "countryChoices",
        "critical_rating": "criticalRatingChoices",
        "day": "dayChoices",
        "description": "descriptionChoices",
        "format": "formatChoices",
        "issue": "issueChoices",
        "language": "languageChoices",
        "maturity_rating": "maturityRatingChoices",
        "month": "monthChoices",
        "notes": "notesChoices",
        "read_ltr": "readLTRChoices",
        "scan_info": "scanInfoChoices",
        "summary": "summaryChoices",
        "title": "titleChoices",
        "user_rating": "userRatingChoices",
        "web": "webChoices",
        "year": "yearChoices",
        "series.volume_count": "volumeCountChoices",
        "volume.issue_count": "issueCountChoices",
    }

    TEXT_AREA_KEYS = set(("summary", "description", "notes"))

    def query_container(self):
        """Return container aggregate data and comic pks."""

        # Create the aggregates like we do for the browser
        group = self.kwargs["group"]
        pk = self.kwargs["pk"]

        model = self.GROUP_MODEL[group]
        aggregate_filter = self.get_aggregate_filter()

        obj = model.objects.filter(pk=pk)
        if model != Comic:
            agg_func = self.get_aggregate_func("size", model, aggregate_filter)
            obj = obj.annotate(size=agg_func)
        order_key = self.params.get("sort_by", self.DEFAULT_ORDER_KEY)
        obj = self.annotate_cover_path(obj, model, aggregate_filter, order_key)
        obj = self.annotate_children_and_page_count(obj, aggregate_filter)
        obj = self.annotate_bookmarks(obj)
        obj = self.annotate_progress(obj)
        obj = obj.annotate(
            x_comic=FilteredRelation("comic", condition=aggregate_filter)
        )
        # Get the values as a dict
        container_values = obj.values(*self.CONTAINER_VALUES)

        # Copy the values into a dict with serializer names
        comic_summary = {"pks": set()}
        for obj in container_values:
            comic_summary["pks"].add(obj.get("x_comic__pk"))
        first_obj = container_values[0]
        for (
            query_key,
            serializer_key,
        ) in self.CONTAINER_AGG_SERIALIZER_MAP.items():
            comic_summary[serializer_key] = first_obj.get(query_key)

        return comic_summary

    @staticmethod
    def ensure_collection(comic_summary, serializer_key, comic_pk, collection_type):
        """Ensure a set or dict exists to populate."""
        if serializer_key not in comic_summary:
            comic_summary[serializer_key] = dict()

        if comic_pk not in comic_summary[serializer_key]:
            comic_summary[serializer_key][comic_pk] = collection_type()

    def query_comics(self, pks):
        """
        Aggregate comic data in python because sqllite doesn't have array
        fields.
        """
        comics = Comic.objects.filter(pk__in=pks).prefetch_related()
        comic_summary = {"pks": set()}
        for comic in comics:
            comic_summary["pks"].add(comic.pk)
            # FIELDS
            for (
                long_field,
                serializer_key,
            ) in self.COMIC_FIELD_SERIALIZER_MAP.items():
                # Add the value to a set
                self.ensure_collection(comic_summary, serializer_key, comic.pk, set)
                fields = long_field.split(".")
                relation = comic
                for field in fields:
                    # walk the relation chain
                    value = getattr(relation, field, None)
                    relation = value
                comic_summary[serializer_key][comic.pk].add(value)
            # FKS WITH NAMES
            for (
                relation,
                serializer_key,
            ) in self.COMIC_FK_SERIALIZER_MAP.items():
                self.ensure_collection(comic_summary, serializer_key, comic.pk, dict)
                obj = getattr(comic, relation)
                value = obj.pk
                text = obj.name
                comic_summary[serializer_key][comic.pk][value] = text
            # MANY TO MANY RELATIONS WITH PKS & NAMES
            for (
                relation,
                serializer_key,
            ) in self.COMIC_M2M_SERIALIZER_MAP.items():
                self.ensure_collection(comic_summary, serializer_key, comic.pk, dict)
                m2m = getattr(comic, relation)
                for obj in m2m.all():
                    value = obj.pk
                    text = obj.name
                    comic_summary[serializer_key][comic.pk][value] = text
            # CREDITS ARE SPECIAL M2M RELATIONS
            for credit in comic.credits.all():
                self.ensure_collection(comic_summary, "credit_summary", comic.pk, dict)
                # expand the credit object later if needed.
                comic_summary["credit_summary"][comic.pk][credit.pk] = credit
        return comic_summary

    @staticmethod
    def dict_to_vue_choices(rel_dict):
        """transform a pk -> value dict into a vue_choice."""
        choices = []
        if rel_dict:
            for value, text in rel_dict.items():
                vue_choice = {"value": value, "text": text}
                choices.append(vue_choice)
        if len(choices) == 0 or len(choices) == 1 and choices[0]["value"] is None:
            choices = None
        return choices

    @staticmethod
    def credit_vue_choice(obj):
        """Create a vue choice from a db object with a pk and name."""
        return {"value": obj.pk, "text": obj.name}

    def pre_serialize(self, comic_summary):
        """
        If aggregated sets or dicts for all comics are identical return
        only one of them. Otherwise return null.
        """
        # TODO: most of this will be rewritten in APIv2

        # LISTS OF VALUES
        for serializer_key in self.COMIC_FIELD_SERIALIZER_MAP.values():
            last_set = None
            for value_set in comic_summary[serializer_key].values():
                if last_set is not None and value_set != last_set:
                    last_set = None
                    break
                last_set = value_set
            if last_set == set([None]):
                last_set = None
            comic_summary[serializer_key] = last_set

        # PK TO NAME DICTS TRANSFORM INTO VUE CHOICES
        for serializer_key in self.VUE_CHOICE_KEYS:
            last_dict = None
            for value_dict in comic_summary[serializer_key].values():
                if last_dict is not None and value_dict.keys() != last_dict.keys():
                    last_dict = None
                    break
                last_dict = value_dict
            comic_summary[serializer_key] = self.dict_to_vue_choices(last_dict)

        # CREDITS ARE SPECIAL VUE CHOICES
        last_credit_dict = None
        credit_summary = comic_summary.get("credit_summary")
        if credit_summary:
            for credit_dict in comic_summary["credit_summary"].values():
                if (
                    last_credit_dict is not None
                    and credit_dict.keys() != last_credit_dict.keys()
                ):
                    last_credit_dict = None
                    break
                last_credit_dict = credit_dict
            comic_summary["credit_summary"] = None

            # CREDIT TO VUE CHOICE TRANSFORM
            if last_credit_dict:
                credit_choices = []
                for pk, credit in last_credit_dict.items():
                    value = {
                        "pk": pk,
                        "person": self.credit_vue_choice(credit.person),
                        "role": self.credit_vue_choice(credit.role),
                    }
                    credit_choices.append(value)
            else:
                credit_choices = None

            comic_summary["creditsChoices"] = credit_choices

        # Text Areas can't select choices, and they're big so only pass
        # them through if there's one of them.
        for key in self.TEXT_AREA_KEYS:
            choices_key = f"{key}Choices"
            choices = comic_summary.get(choices_key)
            if choices and len(choices) == 1:
                comic_summary[key] = choices.pop()
            else:
                comic_summary[key] = None

        return comic_summary

    @staticmethod
    def report_time(start_time, num_comics):
        """
        Calculate how long it takes per comic to aggregate metadata.
        Used in the magic number for the progress circle.
        """
        elapsed = time.time() - start_time
        cps = num_comics / elapsed
        LOG.debug(f"{num_comics} comics / {elapsed:.2g} secs = {cps:.2g} CPS")

    def get(self, request, *args, **kwargs):
        """Get metadata for a single comic."""
        start_time = time.time()
        # Init
        self.params = self.get_session(self.BROWSE_KEY)

        container = self.query_container()
        comic_data = self.query_comics(container["pks"])
        comic_summary = self.pre_serialize(comic_data)
        comic_summary.update(container)

        serializer = MetadataSerializer(comic_summary)
        if DEBUG:
            self.report_time(start_time, len(container["pks"]))

        return Response(serializer.data)
