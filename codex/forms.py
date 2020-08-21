"""Codex django forms."""
from enum import Enum

from django import forms
from django.utils.translation import gettext_lazy as _

from codex.models import AdminFlag
from codex.models import Character
from codex.models import Comic
from codex.models import EnumChoice
from codex.models import FitToChoice


class BookmarkFilterChoice(EnumChoice):
    """Valid choices for filtering the view by bookmark."""

    ALL = _("All")
    UNREAD = _("Unread")
    IN_PROGRESS = _("In Progress")


class SortChoice(EnumChoice):
    """Valid choices for sorting the view."""

    sort_name = _("Name")
    date = _("Date Published")
    created_at = _("Date Added")
    page_count = _("Page Count")
    size = _("File Size")
    user_rating = _("User Rating")
    critical_rating = _("Critical Rating")


# Making these part of the mixin classes didn't work.
BOOKMARK_FILTER = forms.ChoiceField(
    choices=BookmarkFilterChoice.get_choices(),
    widget=forms.Select(),
    label="Filters",
    required=False,
)

DECADE_FILTER = forms.MultipleChoiceField(
    choices=[],  # dynamic
    widget=forms.SelectMultiple(),
    label="Decade",
    required=False,
)
CHARACTER_FILTER = forms.MultipleChoiceField(
    choices=[],  # dynamic
    widget=forms.SelectMultiple(),
    label="Character",
    required=False,
)
ROOT_GROUP = forms.ChoiceField(
    choices=[], widget=forms.Select(), label="Group", required=False,
)
SORT_BY = forms.ChoiceField(
    choices=SortChoice.get_choices(),
    widget=forms.Select(),
    label="Sort",
    required=False,
)
SORT_REVERSE = forms.BooleanField(label="Reverse", required=False)


class DecadeFilterMixin:
    """Mixin for decade filters forms."""

    def _init_decade_filter(self):
        """Get the decades in the db."""
        decades = (
            Comic.objects.all()
            .values_list("decade", flat=True)
            .distinct()
            .order_by("decade")
        )
        decade_choices = []
        for decade in decades:
            if decade is None:
                # None value translates to "" in the form. Hack around that
                decade_choices.append((-1, "None"))
            else:
                decade_choices.append((decade, decade))
        self.fields["decade_filter"].choices = decade_choices


class CharacterFilterMixin:
    """Mixin for character filters forms."""

    def _init_character_filter(self):
        """Get the characters from the db."""
        choices = Character.objects.all().values_list("pk", "name").order_by("name")
        self.fields["character_filter"].choices = choices


class BookmarkFiltersForm(forms.Form):
    """Boolean filters form for template."""

    bookmark_filter = BOOKMARK_FILTER


class BrowseDecadeFilterForm(forms.Form, DecadeFilterMixin):
    """Decade filters form for template."""

    decade_filter = DECADE_FILTER

    def __init__(self, *args, **kwargs):
        """Initialize dynamic choices."""
        super().__init__(*args, **kwargs)
        self._init_decade_filter()


class BrowseCharacterFilterForm(forms.Form, CharacterFilterMixin):
    """Characters filter form for template."""

    character_filter = CHARACTER_FILTER

    def __init__(self, *args, **kwargs):
        """Initialize dynamic choices."""
        super().__init__(*args, **kwargs)
        self._init_character_filter()


class GroupMixin:
    """Mixin for group selection."""

    class GroupChoice(Enum):
        """Valid choices for grouping the view."""

        r = _("Publishers")
        p = _("Imprints")
        i = _("Series")
        s = _("Volumes")
        v = _("Issues")
        f = _("Folder View")

    HIDE_PUBLISHERS = {"r": None, "p": _("Publishers + Imprints")}
    HIDE_SERIES = {"s": None, "i": _("Series + Volumes")}

    @classmethod
    def get_group_name(cls, group, settings, show_folders):
        """Get the display name of the group for the curren settings."""
        show_publishers = settings.get("show_publishers")
        show_series = settings.get("show_series")
        if not show_publishers and group in cls.HIDE_PUBLISHERS.keys():
            value = cls.HIDE_PUBLISHERS[group]
        elif not show_series and group in cls.HIDE_SERIES.keys():
            value = cls.HIDE_SERIES[group]
        elif group == "f" and not show_folders:
            value = None
        else:
            value = cls.GroupChoice[group].value
        return value

    @classmethod
    def get_group_choices(cls, settings, show_folders):
        """Dynamically get the choices according to settings."""
        choices = []
        for data in cls.GroupChoice:
            value = cls.get_group_name(data.name, settings, show_folders)
            if value:
                choices.append((data.name, value))
        return choices

    def _init_root_group_choices(self, settings):
        """Initialize dynamic choices."""
        enable_fv, _ = AdminFlag.objects.get_or_create(
            name=AdminFlag.ENABLE_FOLDER_VIEW
        )
        self.fields["root_group"].choices = self.get_group_choices(
            settings, enable_fv.on
        )


class BrowseGroupForm(forms.Form, GroupMixin):
    """Browse group form for template."""

    def __init__(self, settings, *args, **kwargs):
        """Initialize dynamic choices."""
        super().__init__(*args, **kwargs)
        self._init_root_group_choices(settings)

    root_group = ROOT_GROUP


class BrowseSortForm(forms.Form):
    """Sort form for template."""

    sort_by = SORT_BY
    sort_reverse = SORT_REVERSE


class BrowseForm(forms.Form, DecadeFilterMixin, CharacterFilterMixin, GroupMixin):
    """Big syncretic form for validation using FormView."""

    bookmark_filter = BOOKMARK_FILTER
    decade_filter = DECADE_FILTER
    character_filter = CHARACTER_FILTER
    root_group = ROOT_GROUP
    sort_by = SORT_BY
    sort_reverse = SORT_REVERSE
    """The big browser preferences form."""

    def __init__(self, settings, *args, **kwargs):
        """Initialize dynamic choices."""
        super().__init__(*args, **kwargs)
        self._init_character_filter()
        self._init_decade_filter()
        self._init_root_group_choices(settings)


class MarkReadForm(forms.Form):
    """Mark Comics and Containers read or unread."""

    read = forms.BooleanField(label="Read", required=False)
    next_url = forms.CharField(widget=forms.HiddenInput())
    root_path_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)


class BrowseSettingsForm(forms.Form):
    """User settings form."""

    show_publishers = forms.BooleanField(label="Show Publisher level", required=False)
    show_series = forms.BooleanField(label="Show Series level", required=False)


class ReaderForm(forms.Form):
    """Form for the reader options."""

    def __init__(self, page_count=999, *args, **kwargs):
        """Set the max value of the goto field on initialization."""
        super().__init__(*args, **kwargs)
        self.fields["goto"].max_value = page_count - 1

    fit_to = forms.ChoiceField(
        choices=FitToChoice.get_choices(),
        label="Fit to",
        widget=forms.Select(),
        required=False,
    )
    two_pages = forms.BooleanField(label="Two page spread", required=False)
    make_default = forms.BooleanField(label="Make Default", required=False)
    goto = forms.IntegerField(label="Go to page", min_value=0, required=False)
    goto.widget.attrs.update(size="3")
