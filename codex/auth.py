"""Registration with saving the session."""
from django_registration.backends.one_step.views import RegistrationView

from codex.models import UserBookmark


class RegistrationView(RegistrationView):
    """Registration with saving the session."""

    def register(self, form):
        """
        Save the session stuff before login.

        A bit hacky since it super.register() saves the form again.
        """
        session_key = self.request.session.session_key
        user = form.save()
        UserBookmark.objects.filter(session__session_key=session_key).update(user=user)
        return super().register(form)
