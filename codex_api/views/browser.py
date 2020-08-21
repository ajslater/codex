"""Views for browsing comic library."""
import logging

from bidict import bidict
from django.db.models import Avg
from django.db.models import BooleanField, CharField
from django.db.models import Count
from django.db.models import DecimalField
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
from rest_framework.views import APIView
from stringcase import snakecase

from codex_api.choices.model import CharactersFilterChoice
from codex_api.choices.model import DecadeFilterChoice
from codex_api.models import AdminFlag
from codex_api.models import Comic
from codex_api.models import Folder
from codex_api.models import Imprint
from codex_api.models import Library
from codex_api.models import Publisher
from codex_api.models import Series
from codex_api.models import Volume
from codex_api.serializers.browse import BrowseListSerializer
from codex_api.serializers.browse import BrowserOpenedSerializer
from codex_api.serializers.browse import BrowserSettingsSerializer
from codex_api.views.mixins import SessionMixin
from codex_api.views.mixins import UserBookmarkMixin


LOG = logging.getLogger(__name__)


class BrowseView(APIView, SessionMixin, UserBookmarkMixin):
    """Browse comics with a variety of filters and sorts."""

    FOLDER_GROUP = "f"
    COMIC_GROUP = "c"
    GROUP_MODEL = bidict(
        {
            "r": None,
            "p": Publisher,
            "i": Imprint,
            "s": Series,
            "v": Volume,
            COMIC_GROUP: Comic,
            FOLDER_GROUP: Folder,
        }
    )
    GROUP_SHOW_FLAGS = (
        "r",
        "p",
        "i",
        "s",
        "v",
    )
    GROUP_RELATION = {
        "p": "publisher",
        "i": "imprint",
        "s": "series",
        "v": "volume",
        "c": "comic",
    }
    FILTER_ATTRIBUTES = ("decade", "characters")
    SORT_AGGREGATE_FUNCS = {
        "user_rating": Avg,
        "critical_rating": Avg,
        "size": Sum,
        "date": Max,
        "updated_at": Max,
    }

    def get_valid_groups(self):
        """Get the valid groups for the settings."""
        root_group = self.params["root_group"]
        valid_groups = []
        below_root_group = False
        for group_key in self.GROUP_SHOW_FLAGS:
            enabled = (
                below_root_group and self.params["show"].get(group_key)
            ) or group_key == root_group
            if enabled:
                valid_groups.append(group_key)
            if group_key == root_group:
                below_root_group = True

        return valid_groups

    def filter_by_comic_many_attribute(self, attribute):
        """Filter by a comic any2many attribute."""
        filter_list = self.params["filters"].get(attribute)
        filter_query = Q()
        if filter_list:
            # None values in a list don't work right so test for them
            #   seperately
            for index, val in enumerate(filter_list):
                if val is None:
                    del filter_list[index]
                    filter_query |= Q(**{f"comic__{attribute}": None})
            if filter_list:
                filter_query |= Q(**{f"comic__{attribute}__in": filter_list})
        return filter_query

    def get_comic_attribute_filter(self):
        """Filter the comics based on the form filters."""
        comic_attribute_filter = Q()
        for attribute in self.FILTER_ATTRIBUTES:
            comic_attribute_filter &= self.filter_by_comic_many_attribute(attribute)
        return comic_attribute_filter

    def get_bookmark_filter(self):
        """Build bookmark query."""
        choice = self.params["filters"].get("bookmark", "ALL")

        bookmark_filter = Q()
        if choice in ("UNREAD", "IN_PROGRESS",):
            bookmark_filter &= (
                Q(comic__userbookmark__finished=False)
                | Q(comic__userbookmark=None)
                | Q(comic__userbookmark__finished=None)
            )
            if choice == "IN_PROGRESS":
                bookmark_filter &= Q(comic__userbookmark__bookmark__gt=0)
        return bookmark_filter

    def get_order_by(self, order_key):
        """
        Create the order_by list.

        Order on pk to give duplicates a consistant position.
        """
        sort_reverse = self.params.get("sort_reverse")
        if sort_reverse:
            order_prefix = "-"
        else:
            order_prefix = ""
        return [order_prefix + order_key, order_prefix + "pk"]

    def annotate_and_sort(self, obj_list, model, aggregate_filter):
        """
        Annotations for display and sorting.

        model is neccissary because this gets called twice by folder
        view. once for folders, once for the comics.
        """
        self.model_group = self.GROUP_MODEL.inverse[model]
        obj_list = obj_list.annotate(
            group=Value(self.model_group, CharField(max_length=1))
        )

        if model != Comic:
            # Count children - Display only
            child_count = Count("comic__pk", distinct=True, filter=aggregate_filter)
            obj_list = obj_list.annotate(child_count=child_count).filter(
                child_count__gt=0
            )

            # Hoist up total page_count of children
            # Used for sorting and progress
            page_count = Sum("comic__page_count", filter=aggregate_filter)
            obj_list = obj_list.annotate(page_count=page_count)

        # Annotate progress
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
        obj_list = UserBookmarkMixin.annotate_progress(obj_list)

        # TODO it might be nice to add get_unique_name here for
        # duplicate objects

        # Select comics for the children by an outer ref for annotation
        # Order the decendent comics by the sort argumentst
        order_key = self.params.get("sort_by")

        if model != Comic:
            # Cover Path from sorted children.
            # XXX Don't know how to make this a join
            #   because it selects by order_by but wants the cover_path
            model_container_filter = Q(**{model.__name__.lower(): OuterRef("pk")})
            comics = Comic.objects.all()
            comics = comics.filter(model_container_filter)
            comics = comics.filter(aggregate_filter)
            order_by = self.get_order_by(order_key)
            comics = comics.order_by(*order_by).values("cover_path")
            cover_path_subquery = Subquery(comics[:1])
            obj_list = obj_list.annotate(cover_path=cover_path_subquery)

            # Sortable aggregates
            agg_func = self.SORT_AGGREGATE_FUNCS.get(order_key)
            if agg_func:
                agg_relation = "comic__" + order_key
                if order_key in ("updated_at",):
                    order_key = "child_" + order_key
                obj_list = obj_list.annotate(
                    **{order_key: agg_func(agg_relation, filter=aggregate_filter)}
                )

        # order the containers by the sort arguments
        order_by = self.get_order_by(order_key)

        obj_list = obj_list.order_by(*order_by)
        return obj_list

    def get_parent_folder_filter(self):
        """Create the folder and comic object lists."""
        pk = self.kwargs.get("pk")
        if pk:
            self.host_folder = Folder.objects.get(pk=pk)
        else:
            self.host_folder = None

        return Q(parent_folder=self.host_folder)

    def get_folders_filter(self):
        """Create the folder and comic object lists."""
        pk = self.kwargs.get("pk")
        if pk:
            folders_filter = Q(folder__in=[pk])
        else:
            folders_filter = Q()

        return folders_filter

    def set_browse_model(self):
        """Set the model for the browse list."""
        group = self.kwargs.get("group")
        self.group_class = self.GROUP_MODEL[group]

        # find for browse groups
        valid_model_groups = self.get_valid_groups()
        valid_model_groups.append(self.COMIC_GROUP)
        found_group = False
        for g in valid_model_groups:
            child_group = g
            if found_group:
                break
            if g == group:
                found_group = True

        self.model = self.GROUP_MODEL[child_group]

    def get_browse_container_filter(self):
        """Get the objects we'll be displaying."""
        # Get the instances that are children of the group_instance
        # And the filtered comics that are children of the group_instance
        pk = self.kwargs.get("pk")
        if pk > 0:
            group = self.kwargs.get("group")
            group_relation = self.GROUP_RELATION[group]
            container_filter = Q(**{group_relation: pk})
        else:
            container_filter = Q()

        return container_filter

    def get_query_filters(self, container_filter):
        """Return the main object filter and the one for aggregates."""
        bookmark_filter_join = self.get_bookmark_filter()
        comic_attribute_filter = self.get_comic_attribute_filter()
        aggregate_filter = bookmark_filter_join & comic_attribute_filter
        object_filter = container_filter & aggregate_filter
        return object_filter, aggregate_filter

    def get_folder_queryset(self):
        """Create folder queryset."""
        object_filter, aggregate_filter = self.get_query_filters(
            self.get_parent_folder_filter()
        )

        # Create the main queries with filters
        folder_list = Folder.objects.filter(object_filter)
        comic_list = Comic.objects.filter(object_filter).select_related()
        # Create a query for comics used by the model filters
        self.choices_comic_list = Comic.objects.filter(
            aggregate_filter & self.get_folders_filter()
        )

        # add annotations for display and sorting
        # and the comic_cover which uses a sort
        folder_list = self.annotate_and_sort(folder_list, Folder, aggregate_filter)
        comic_list = self.annotate_and_sort(comic_list, Comic, aggregate_filter)

        return folder_list, comic_list

    def get_browse_queryset(self):
        """Create and browse queryset."""
        self.set_browse_model()

        # Create the main query with the filters
        object_filter, aggregate_filter = self.get_query_filters(
            self.get_browse_container_filter()
        )
        obj_list = self.model.objects.filter(object_filter)
        # for the model filter choices that don't need annotations
        self.choices_comic_list = Comic.objects.filter(object_filter)
        # obj_list filtering done

        # Add annotations for display and sorting
        obj_list = self.annotate_and_sort(obj_list, self.model, aggregate_filter)
        if self.model == Comic:
            container_list = tuple()
            comic_list = obj_list
        else:
            container_list = obj_list
            comic_list = tuple()
        return container_list, comic_list

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
        for group_key in self.valid_groups:
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
            header = self.group_instance.header_name
            if header:
                browse_title += header + " "
            browse_title += self.group_instance.display_name
        return browse_title

    def get_context(self):
        """Get result data."""
        if self.params.get("root_group") == self.FOLDER_GROUP:
            up_group, up_pk = self.get_folder_up_route()
            browse_title = self.get_folder_title()
        else:
            self.set_group_instance()
            up_group, up_pk = self.get_browse_up_route()
            browse_title = self.get_browse_title()

        if up_group is not None and up_pk is not None:
            up_route = {"group": up_group, "pk": up_pk}
        else:
            up_route = None

        decade_filter_choices = DecadeFilterChoice.get_vue_choices(
            self.choices_comic_list
        )
        characters_filter_choices = CharactersFilterChoice.get_vue_choices(
            self.choices_comic_list
        )

        admin_flags = AdminFlag.objects.filter(name__in=AdminFlag.FLAG_NAMES).values(
            "name", "on"
        )
        admin = {}
        for obj in admin_flags:
            admin[obj.get("name")] = obj.get("on")

        efv_flag = AdminFlag.objects.get(name=AdminFlag.ENABLE_FOLDER_VIEW)

        context = {
            "upRoute": up_route,
            "browseTitle": browse_title,
            "containerList": self.container_list,
            "comicList": self.comic_list,
            "formChoices": {
                "decade": decade_filter_choices,
                "characters": characters_filter_choices,
                "enableFolderView": efv_flag.on,
            },
        }
        return context

    def validate_folder_settings(self):
        """Check that all the view variables for folder mode are set right."""
        if not AdminFlag.objects.get(name=AdminFlag.ENABLE_FOLDER_VIEW).on:
            # 403 should redirect on the client side.
            raise PermissionDenied("folder view disabled")

    def validate_browse_settings(self):
        """Check that all the view variables for browser mode are set right."""
        # Validate Root Group
        group = self.kwargs["group"]
        root_group = self.params.get("root_group")
        if root_group == self.FOLDER_GROUP:
            self.params["root_group"] = root_group = group
            LOG.warn(f"Switched root group from {self.FOLDER_GROUP} to {group}")
        self.valid_groups = self.get_valid_groups()

        for valid_group in self.valid_groups:
            if valid_group == root_group:
                break
            if valid_group == group:
                self.params["root_group"] = root_group = group
                LOG.warn(
                    f"Group '{group}' was a parent of root group "
                    f"'{root_group}'. Reset root group to '{group}'."
                )
                self.valid_groups = self.get_valid_groups()
                break

        # Validate Group
        if group not in self.valid_groups:
            exc = PermissionDenied(detail=f"Asked to show disabled group {group}")
            LOG.exception(exc)
            # 403 should redirect on the client side.
            raise exc

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

    def get_queryset(self):
        """Validate settings and get the queryset."""
        if self.kwargs.get("group") == self.FOLDER_GROUP:
            self.validate_folder_settings()
            self.container_list, self.comic_list = self.get_folder_queryset()
        else:
            self.validate_browse_settings()
            self.container_list, self.comic_list = self.get_browse_queryset()

        self.request.session[self.BROWSE_KEY] = self.params
        self.request.session.save()

        context = self.get_context()
        return context

    def put(self, request, *args, **kwargs):
        """Create the view."""
        self.validate_put(request.data)

        context = self.get_queryset()

        serializer = BrowseListSerializer(context)
        return Response(serializer.data)

    def get(self, request, *args, **kwargs):
        """Get browser settings."""
        self.params = self.get_session(self.BROWSE_KEY)

        context = self.get_queryset()

        filters = self.params["filters"]
        libraries_exist = Library.objects.all().exists()
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
            "browseList": context,
            "librariesExist": libraries_exist,
        }

        serializer = BrowserOpenedSerializer(data)
        return Response(serializer.data)
