"""Codex django forms."""
from enum import Enum

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import RootPath


class FilterChoice(Enum):
    """Valid choices for filtering the view."""

    UNREAD = _("Unread")
    IN_PROGRESS = _("In Progress")
    # YEAR = "Year"
    # GENE = "Genre"
    # WRITER = "Writer"


class GroupChoice(Enum):
    """Valid choices for grouping the view."""

    r = _("Publisher")
    p = _("Imprint")
    i = _("Series")
    s = _("Volume")
    v = _("Issue")
    f = _("Folder View")


class SortChoice(Enum):
    """Valid choices for sorting the view."""

    ALPHANUM = _("Alphabetical")
    DATE = _("Date")


class BrowseForm(forms.Form):
    """The big browser preferences form."""

    filters = forms.MultipleChoiceField(
        choices=[(tag.name, tag.value) for tag in FilterChoice],
        widget=forms.CheckboxSelectMultiple(),
        label="Filters",
        required=False,
    )
    root_group = forms.ChoiceField(
        choices=[(tag.name, tag.value) for tag in GroupChoice],
        widget=forms.RadioSelect(),
        label="Group",
        required=False,
    )
    sort_by = forms.ChoiceField(
        choices=[(tag.name, tag.value) for tag in SortChoice],
        widget=forms.RadioSelect(),
        label="Sort",
        required=False,
    )
    sort_reverse = forms.BooleanField(label="Reverse", required=False)


class ScanRootPathForm(forms.ModelForm):
    """Scan a Single RootPath."""

    force = forms.BooleanField(label="Force", required=False)

    class Meta:
        """No fields, just the id."""

        model = RootPath
        fields = []


class ScanAllForm(forms.Form):
    """Scan All RootPaths."""

    force = forms.BooleanField(label="Force", required=False)
