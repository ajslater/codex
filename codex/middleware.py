"""Django middleware for codex."""

from time import time

from django.db import connection
from django.utils import timezone

from codex.logger.logging import get_logger
from codex.settings.settings import LOG_RESPONSE_TIME, SLOW_QUERY_LIMIT

LOG = get_logger(__name__)


class TimezoneMiddleware:
    """A middleware for fixing django timezones."""

    # https://docs.djangoproject.com/en/dev/topics/i18n/timezones/

    def __init__(self, get_response):
        """Store the creation response."""
        self.get_response = get_response

    def __call__(self, request):
        """Fix timeszone from the django session."""
        if tzname := request.session.get("django_timezone"):
            timezone.activate(tzname)
        else:
            timezone.deactivate()
        return self.get_response(request)


class LogResponseTimeMiddleware:
    """Slow query Middleware."""

    def __init__(self, get_response):
        """Set up get_response func."""
        self.get_response = get_response

    def _log_response_time(self, request):
        """Log response times if slow or debug."""
        start_time = time()
        response = self.get_response(request)
        response_time = time() - start_time
        is_slow = response_time > SLOW_QUERY_LIMIT

        if is_slow or LOG_RESPONSE_TIME:
            msg = f"{response_time}s {request.build_absolute_uri()}"
            if is_slow:
                LOG.warning(msg)
            else:
                LOG.debug(msg)
        return response

    def _log_query_times(self):
        """Log queries if slow or debug."""
        for query in connection.queries:
            is_slow = float(query["time"]) > SLOW_QUERY_LIMIT
            if LOG_RESPONSE_TIME or is_slow:
                msg = f"{query['time']}s {query['sql']}"
                if is_slow:
                    LOG.warning(msg)
                else:
                    LOG.debug(msg)

    def __call__(self, request):
        """Call request."""
        response = self._log_response_time(request)
        self._log_query_times()
        return response
