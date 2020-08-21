"""Codex django forms."""
from django.forms import HiddenInput
from django.forms import IntegerField
from django.forms import ModelForm

from .models import RootPath


class RootPathForm(ModelForm):
    """Form for adding and updating RootPath."""

    def __init__(self, *args, **kwargs):
        """Disable or remove the last scan field."""
        super(RootPathForm, self).__init__(*args, **kwargs)
        instance = getattr(self, "instance", None)
        if instance and instance.id:
            self.fields["id"] = IntegerField()
            self.fields["id"].initial = self.instance.id
            self.fields["id"].widget = HiddenInput()
            self.fields["id"].widget.attrs["readonly"] = "readonly"

    def clean_last_scan_field(self):
        """Protect form ever setting the last scan time."""
        # TODO Unsure if this works
        instance = getattr(self, "instance", None)
        if instance and instance.id:
            return instance.last_scan
        else:
            return self.cleaned_data["last_scan"]

    class Meta:
        """Define the model."""

        model = RootPath
        exclude = ["last_scan"]
