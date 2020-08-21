"""Django views for Codex."""
import logging

from django.urls import reverse_lazy
from django.views.generic import FormView

from codex.forms import BrowseSettingsForm
from codex.views.session import SessionMixin


LOG = logging.getLogger(__name__)


class UserSettingsView(FormView, SessionMixin):
    """User Settings for the session."""

    template_name = "codex/user_settings.html"
    success_url = reverse_lazy("user_settings")
    form_class = BrowseSettingsForm

    def get(self, request, *args, **kwargs):
        """Display the session in the form."""
        initial = self.session_get(self.BROWSE_KEY, "settings")
        form = BrowseSettingsForm(initial=initial)
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def form_valid(self, form):
        """Get the settings and save them to the user session."""
        settings = self.session_get(self.BROWSE_KEY, "settings")
        settings.update(form.cleaned_data)
        self.request.session.save()
        return super().form_valid(form)
