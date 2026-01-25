"""Django middleware for codex."""

from base64 import b64decode
from time import time

from django.db import connection
from django.utils import timezone
from loguru import logger

from codex.settings import LOG_AUTH_HEADERS, LOG_RESPONSE_TIME, SLOW_QUERY_LIMIT


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
                logger.warning(msg)
            else:
                logger.trace(msg)
        return response

    def _log_query_times(self):
        """Log queries if slow or debug."""
        for query in connection.queries:
            is_slow = float(query["time"]) > SLOW_QUERY_LIMIT
            if LOG_RESPONSE_TIME or is_slow:
                msg = f"{query['time']}s {query['sql']}"
                if is_slow:
                    logger.warning(msg)
                else:
                    logger.trace(msg)

    def __call__(self, request):
        """Call request."""
        response = self._log_response_time(request)
        self._log_query_times()
        return response


class LogRequestMiddleware:
    """Log every request."""

    def __init__(self, get_response):
        """Store the creation response."""
        self.get_response = get_response

    def _log_auth_headers(self, request):
        if not LOG_AUTH_HEADERS:
            return
        filtered_headers = {}
        for key, value in request.headers.items():
            if key.lower() in {"user-agent", "authorization", "cookie"}:
                if key.lower().startswith("auth"):
                    parts = value.split(" ")
                    if parts[0] == "Basic":
                        parts[1] = b64decode(parts[1]).decode()
                        final_val = " ".join(parts)
                    else:
                        final_val = value
                else:
                    final_val = value
                filtered_headers[key] = final_val
        logger.trace(filtered_headers)

    def __call__(self, request):
        """Trace the request uri."""
        uri = request.build_absolute_uri()  # Includes query parameters
        logger.trace(uri)
        self._log_auth_headers(request)
        if data := getattr(request, "data", None):
            logger.trace(data)
        return self.get_response(request)
