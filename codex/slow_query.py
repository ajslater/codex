"""Slow query Middleware."""

import os
from time import time

from django.db import connection

from codex.logger.logging import get_logger

LOG = get_logger(__name__)
# limit in seconds
SLOW_QUERY_LIMIT = float(os.environ.get("CODEX_SLOW_QUERY_LIMIT", 0.5))


class SlowQueryMiddleware:
    """Slow query Middleware."""

    def __init__(self, get_response):
        """Set up get_response func."""
        self.get_response = get_response

    def __call__(self, request):
        """Call request."""
        start_time = time()
        response = self.get_response(request)
        response_time = time() - start_time

        if response_time > SLOW_QUERY_LIMIT:
            LOG.warning(
                f"Slow response {response_time} for {request.build_absolute_uri()}"
            )

        # Analyze slow queries after processing the request
        self.analyze_slow_queries()
        return response

    def analyze_slow_queries(self):
        """Analyze slow queries."""
        for query in connection.queries:
            msg = f"{query['time']}: {query['sql']}"
            if float(query["time"]) > SLOW_QUERY_LIMIT:
                LOG.warning(msg)
            # else:
            #    LOG.debug(msg)
