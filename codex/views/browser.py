"""Views for browsing comic library."""
import logging

from bidict import bidict
from django.core.paginator import EmptyPage
from django.core.paginator import Paginator
from django.db.models import Avg
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import Count
from django.db.models import DecimalField
from django.db.models import F
from django.db.models import IntegerField
from django.db.models import Max
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import Subquery
from django.db.models import Sum
from django.db.models import Value
from django.db.models.functions import Cast
from django.db.models.functions import Coalesce
from django.db.models.functions import NullIf
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from stringcase import snakecase

from codex.models import AdminFlag
from codex.models import Comic
from codex.models import Folder
from codex.models import Imprint
from codex.models import Library
from codex.models import Publisher
from codex.models import Series
from codex.models import Volume
from codex.serializers.browse import BrowseListSerializer
from codex.serializers.browse import BrowserOpenedSerializer
from codex.serializers.browse import BrowserSettingsSerializer
from codex.views.browse_base import BrowseBaseView
from codex.views.mixins import UserBookmarkMixin


LOG = logging.getLogger(__name__)


class BrowseView(BrowseBaseView, UserBookmarkMixin):
    """Browse comics with a variety of filters and sorts."""

    COMIC_GROUP = "c"
    GROUP_MODEL = bidict(
        {
            "r": None,
            "p": Publisher,
            "i": Imprint,
            "s": Series,
            "v": Volume,
            COMIC_GROUP: Comic,
            BrowseBaseView.FOLDER_GROUP: Folder,
        }
    )
    GROUP_SHOW_FLAGS = {
        # Show flags to root group equivalients
        "r": "p",
        "p": "i",
        "i": "s",
        "s": "v",
        "v": "c",
    }
    SORT_AGGREGATE_FUNCS = {
        "user_rating": Avg,
        "critical_rating": Avg,
        "size": Sum,
        "date": Max,
        "updated_at": Max,
    }
    DEFAULT_ORDER_KEY = "sort_name"
    CHOICES_RELATIONS = ("decade", "characters")
    MAX_OBJ_PER_PAGE = 100
    ORPHANS = MAX_OBJ_PER_PAGE / 20
    COMMON_BROWSE_FIELDS = [
        "pk",
        "finished",
        "group",
        "library",
        "progress",
        "x_cover_path",
        "header_name",
        "display_name",
        "series_name",
        "volume_name",
        "x_issue",
        "x_path",
        "child_count",
        "bookmark",
    ]

    def get_valid_root_groups(self):
        """
        Valid root groups are determined by the Browser Settings.
        And offset by one group *above* each show flag.
        The volumes root group is always enabled.
        """
        valid_groups = []

        for group_key, show_flag in self.GROUP_SHOW_FLAGS.items():
            enabled = group_key == "v"
            enabled = enabled or self.params["show"].get(show_flag)
            if enabled:
                valid_groups.append(group_key)

        return valid_groups

    def get_valid_nav_groups(self):
        """
        Valid nav groups are the root group and below that are also
        enabled in browser settings.
        """
        root_group = self.params["root_group"]
        valid_groups = []
        below_root_group = False

        for group_key in self.GROUP_SHOW_FLAGS:
            if group_key == root_group:
                enabled = below_root_group = True
            else:
                enabled = below_root_group and self.params["show"].get(group_key)
            if enabled:
                valid_groups.append(group_key)

        return valid_groups

    def get_model_group(self):
        """
        Valid model groups are below the nav group that are also enabled
        in browser settings.
        """
        nav_group = self.kwargs["group"]

        if nav_group == self.FOLDER_GROUP:
            return nav_group

        below_nav_group = False

        for group_key in self.valid_nav_groups:
            if below_nav_group and self.params["show"].get(group_key):
                return group_key
            if group_key == nav_group:
                below_nav_group = True

        return self.COMIC_GROUP

    def get_order_by(self, order_key, model=None):
        """
        Create the order_by list.

        Order on pk to give duplicates a consistant position.
        """
        sort_reverse = self.params.get("sort_reverse")
        if sort_reverse:
            order_prefix = "-"
        else:
            order_prefix = ""
        order_by = [order_prefix + order_key, order_prefix + "pk"]
        if model in (Comic, Folder):
            # This keeps position stability for duplicate comics & folders
            order_by += ["library"]
        return order_by

    def add_annotations(self, obj_list, model, aggregate_filter):
        """
        Annotations for display and sorting.

        model is neccissary because this gets called twice by folder
        view. once for folders, once for the comics.
        """
        ##################
        # Annotate Group #
        ##################
        self.model_group = self.GROUP_MODEL.inverse[model]
        obj_list = obj_list.annotate(
            group=Value(self.model_group, CharField(max_length=1))
        )

        ###########################
        # Annotate children count #
        ###########################
        if model == Comic:
            obj_list = obj_list.annotate(
                child_count=Value(None, IntegerField()),
            )
        else:
            child_count = Count("comic__pk", distinct=True, filter=aggregate_filter)
            obj_list = obj_list.annotate(child_count=child_count).filter(
                child_count__gt=0
            )
            # Hoist up total page_count of children
            # Used for sorting and progress
            page_count = Sum("comic__page_count", filter=aggregate_filter)
            obj_list = obj_list.annotate(page_count=page_count)

        ################################
        # Annotate finished & progress #
        ################################
        ub_filter = self.get_userbookmark_filter()
        # Hoist up: are the children finished or unfinished?
        finished = Cast(
            NullIf(
                Coalesce(
                    Avg(  # distinct average of user's finished values
                        "comic__userbookmark__finished",
                        filter=ub_filter,
                        distinct=True,
                        output_field=DecimalField(),
                    ),
                    False,  # Null db values counted as False
                ),
                Value(0.5),  # Null result if mixed true & false
            ),
            BooleanField(),  # Finally ends up as a ternary boolean
        )
        obj_list = obj_list.annotate(finished=finished)

        # Hoist up the bookmark
        pages_read = Sum("comic__userbookmark__bookmark", filter=ub_filter)
        obj_list = obj_list.annotate(bookmark=pages_read)
        # Annote progress
        obj_list = self.annotate_progress(obj_list)

        #######################
        # Annotate Library Id #
        #######################
        if model not in (Folder, Comic):
            # For folder view stability sorting compatibilty
            obj_list = obj_list.annotate(library=Value(0, IntegerField()))

        order_key = self.params.get("sort_by", self.DEFAULT_ORDER_KEY)

        #######################
        # Annotate Cover Path #
        #######################
        # Select comics for the children by an outer ref for annotation
        # Order the decendent comics by the sort argumentst
        if model == Comic:
            obj_list = obj_list.annotate(x_cover_path=F("cover_path"))
        else:
            # Sortable aggregates
            agg_func = self.SORT_AGGREGATE_FUNCS.get(order_key)
            if agg_func:
                agg_relation = "comic__" + order_key
                if order_key in ("updated_at",):
                    order_key = "child_" + order_key
                obj_list = obj_list.annotate(
                    **{order_key: agg_func(agg_relation, filter=aggregate_filter)}
                )

            # Cover Path from sorted children.
            # XXX Don't know how to make this a join
            #   because it selects by order_by but wants the cover_path
            model_container_filter = Q(**{model.__name__.lower(): OuterRef("pk")})
            comics = Comic.objects.all()
            comics = comics.filter(model_container_filter)
            comics = comics.filter(aggregate_filter)
            order_by = self.get_order_by(order_key)
            cover_comic_path = comics.order_by(*order_by).values("cover_path")
            cover_path_subquery = Subquery(cover_comic_path[:1])
            obj_list = obj_list.annotate(x_cover_path=cover_path_subquery)

        #######################
        # Annotate name fields #
        #######################
        # XXX header_name & display_name might be better done on import.
        if model in (Publisher, Series, Folder, Comic):
            obj_list = obj_list.annotate(header_name=Value(None, CharField()))
        elif model == Imprint:
            obj_list = obj_list.annotate(header_name=F("publisher__name"))
        elif model == Volume:
            obj_list = obj_list.annotate(header_name=F("series__name"))

        if model == Comic:
            obj_list = obj_list.annotate(
                series_name=F("series__name"),
                volume_name=F("volume__name"),
                x_issue=F("issue"),
                x_path=F("path"),
            )
        else:
            obj_list = obj_list.annotate(
                series_name=Value(None, CharField()),
                volume_name=Value(None, CharField()),
                x_issue=Value(None, CharField()),
                x_path=Value(None, CharField()),
            )

        if model in (Publisher, Imprint, Series, Volume, Folder):
            obj_list = obj_list.annotate(display_name=F("name"))
        elif model == Comic:
            # XXX should probably change title to name in comic model
            obj_list = obj_list.annotate(display_name=F("title"))

        return obj_list

    def set_browse_model(self):
        """Set the model for the browse list."""
        group = self.kwargs.get("group")
        self.group_class = self.GROUP_MODEL[group]

        model_group = self.get_model_group()
        self.model = self.GROUP_MODEL[model_group]

    def get_value_fields(self):
        """Get the only fields we care about for this object."""
        order_key = self.params.get("sort_by", self.DEFAULT_ORDER_KEY)
        fields = self.COMMON_BROWSE_FIELDS + [order_key]
        return fields

    def get_folder_queryset(self, object_filter, aggregate_filter):
        """Create folder queryset."""
        # Create the main queries with filters
        folder_list = Folder.objects.filter(object_filter)
        comic_list = Comic.objects.filter(object_filter)

        # add annotations for display and sorting
        # and the comic_cover which uses a sort
        folder_list = self.add_annotations(folder_list, Folder, aggregate_filter)
        comic_list = self.add_annotations(comic_list, Comic, aggregate_filter)

        # Reduce to values for concatenation
        fields = self.get_value_fields()
        folder_list = folder_list.values(*fields)
        comic_list = comic_list.values(*fields)
        obj_list = folder_list.union(comic_list)

        return obj_list

    def get_browse_queryset(self, object_filter, aggregate_filter):
        """Create and browse queryset."""
        obj_list = self.model.objects.filter(object_filter)
        # obj_list filtering done

        # Add annotations for display and sorting
        obj_list = self.add_annotations(obj_list, self.model, aggregate_filter)

        # Convert to a dict to be compatible with Folder View concatenate
        fields = self.get_value_fields()
        obj_list = obj_list.values(*fields)

        return obj_list

    def get_folder_up_route(self):
        """Get out parent's pk."""
        up_pk = None

        # Recall root id & relative path from way back in
        # object creation
        if self.host_folder:
            if self.host_folder.parent_folder:
                up_pk = self.host_folder.parent_folder.pk
            else:
                up_pk = 0

        return self.FOLDER_GROUP, up_pk

    def get_folder_title(self):
        """Get the title for folder view."""
        if self.host_folder:
            browse_title = self.host_folder.name
        else:
            browse_title = "Root"
        return browse_title

    def set_group_instance(self):
        """Create group_class instance."""
        pk = self.kwargs.get("pk")
        if pk > 0:
            self.group_instance = self.group_class.objects.select_related().get(pk=pk)
        else:
            self.group_instance = None

    def get_browse_up_route(self):
        """Get the up route from the first valid ancestor."""
        group = self.kwargs.get("group")

        # Ancestor group
        ancestor_group = None
        for group_key in self.valid_nav_groups:
            if group_key == group:
                break
            ancestor_group = group_key

        # Ancestor pk
        if ancestor_group is None:
            ancestor_pk = None
        elif ancestor_group == self.params["root_group"] or self.kwargs.get("pk") == 0:
            ancestor_pk = 0
        else:
            # get the ancestor pk from the current group
            ancestor_relation = self.GROUP_RELATION[ancestor_group]
            ancestor_pk = getattr(self.group_instance, ancestor_relation).pk

        return ancestor_group, ancestor_pk

    def get_browse_title(self):
        """Get the proper title for this browse level."""
        pk = self.kwargs.get("pk")
        group = self.kwargs.get("group")
        if group == self.params["root_group"] or pk == 0:
            browse_title = self.model.PLURAL
        else:
            browse_title = ""
            # XXX this duplicates the logic that annotates the header_name
            #     for the obj_list
            #     should probably move this all to the front end
            if self.group_class == Imprint:
                header = self.group_instance.publisher.name
            elif self.group_class == Volume:
                header = self.group_instance.series.name
            else:
                header = ""

            if header:
                browse_title += header + " "

            if self.group_class == Volume:
                volume_name = self.group_instance.name
                if volume_name:
                    if len(volume_name) == 4 and volume_name.isdigit():
                        volume_name = f"({volume_name})"
                    else:
                        volume_name = f"v{volume_name}"

                    browse_title += volume_name

                    volume_count = self.group_instance.series.volume_count
                    if volume_count:
                        header += f" of {volume_count}"
                else:
                    browse_title += "v0"
            else:
                browse_title += self.group_instance.name

        return browse_title

    def raise_valid_route(self, message):
        """403 should redirect to the valid group on the client side."""
        valid_group = self.valid_nav_groups[0]
        raise PermissionDenied({"group": valid_group, "message": message})

    def validate_folder_settings(self):
        """Check that all the view variables for folder mode are set right."""
        if not AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_FOLDER_VIEW).on:
            self.valid_nav_groups = self.get_valid_nav_groups()
            raise self.raise_valid_route("folder view disabled")

    def validate_browse_settings(self):
        """Check that all the view variables for browser mode are set right."""
        # Validate Root Group
        group = self.kwargs["group"]
        root_group = self.params.get("root_group")
        if root_group == self.FOLDER_GROUP:
            self.params["root_group"] = root_group = group
            LOG.warn(f"Switched root group from {self.FOLDER_GROUP} to {group}")
        else:
            valid_root_groups = self.get_valid_root_groups()
            if root_group not in valid_root_groups:
                if group in valid_root_groups:
                    self.params["root_group"] = root_group = group
                else:
                    self.params["root_group"] = valid_root_groups[0]
                LOG.warn(f"Reset root group to {self.params['root_group']}")

        # Validate Group
        self.valid_nav_groups = self.get_valid_nav_groups()
        if group not in self.valid_nav_groups:
            self.raise_valid_route(f"Asked to show disabled group {group}")

    def validate_put(self, data):
        """Validate submitted settings."""
        serializer = BrowserSettingsSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as ex:
            LOG.error(serializer.errors)
            LOG.exception(ex)
            raise ex

        self.params = {}
        for key, value in serializer.validated_data.items():
            snake_key = snakecase(key)
            self.params[snake_key] = value

    def get_browse_list(self):
        """Validate settings and get the querysets."""

        if self.kwargs.get("group") == self.FOLDER_GROUP:
            self.validate_folder_settings()
        else:
            self.validate_browse_settings()

        self.set_browse_model()
        # Create the main query with the filters
        object_filter, aggregate_filter = self.get_query_filters()

        if self.kwargs.get("group") == self.FOLDER_GROUP:
            obj_list = self.get_folder_queryset(object_filter, aggregate_filter)
        else:
            obj_list = self.get_browse_queryset(object_filter, aggregate_filter)

        # Order
        order_key = self.params.get("sort_by", self.DEFAULT_ORDER_KEY)
        order_by = self.get_order_by(order_key, self.model)
        obj_list = obj_list.order_by(*order_by)

        # Pagination
        paginator = Paginator(obj_list, self.MAX_OBJ_PER_PAGE, orphans=self.ORPHANS)
        page = self.kwargs.get("page")
        if page < 1:
            page = 1
        try:
            obj_list = paginator.page(page).object_list
        except EmptyPage:
            LOG.warn("No items on page {page}")
            obj_list = paginator.page(1).object_list

        self.request.session[self.BROWSE_KEY] = self.params
        self.request.session.save()

        # get additional context
        if self.kwargs.get("group") == self.FOLDER_GROUP:
            up_group, up_pk = self.get_folder_up_route()
            browse_title = self.get_folder_title()
        else:
            self.set_group_instance()
            up_group, up_pk = self.get_browse_up_route()
            browse_title = self.get_browse_title()

        if up_group is not None and up_pk is not None:
            up_route = {"group": up_group, "pk": up_pk, "page": 1}
        else:
            up_route = {}

        efv_flag = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_FOLDER_VIEW)

        libraries_exist = Library.objects.exists()

        # construct final data structure
        browse_list = {
            "upRoute": up_route,
            "browseTitle": browse_title,
            "objList": obj_list,
            "numPages": paginator.num_pages,
            "formChoices": {"enableFolderView": efv_flag.on},
            "librariesExist": libraries_exist,
        }
        return browse_list

    def put(self, request, *args, **kwargs):
        """Create the view."""
        self.validate_put(request.data)

        browse_list = self.get_browse_list()

        serializer = BrowseListSerializer(browse_list)
        return Response(serializer.data)

    def get(self, request, *args, **kwargs):
        """Get browser settings."""
        self.params = self.get_session(self.BROWSE_KEY)

        browse_list = self.get_browse_list()

        filters = self.params["filters"]
        data = {
            "settings": {
                "filters": {
                    "bookmark": filters.get("bookmark"),
                    "decade": filters.get("decade"),
                    "characters": filters.get("characters"),
                },
                "rootGroup": self.params.get("root_group"),
                "sortBy": self.params.get("sort_by"),
                "sortReverse": self.params.get("sort_reverse"),
                "show": self.params.get("show"),
            },
            "browseList": browse_list,
        }

        serializer = BrowserOpenedSerializer(data)
        return Response(serializer.data)
