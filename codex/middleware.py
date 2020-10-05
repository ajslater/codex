"""Django middleware for codex."""
# https://docs.djangoproject.com/en/3.1/topics/i18n/timezones/
from django.utils import timezone


class TimezoneMiddleware:
    """A middleware for fixing django timezones."""

    def __init__(self, get_response):
        """Store the creation response."""
        self.get_response = get_response

    def __call__(self, request):
        """Fix timeszone from the django session."""
        tzname = request.session.get("django_timezone")
        if tzname:
            timezone.activate(tzname)
        else:
            timezone.deactivate()
        return self.get_response(request)
