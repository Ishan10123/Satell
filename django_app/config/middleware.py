import logging

from django.db import OperationalError
from django.http import HttpResponse


logger = logging.getLogger("django.request")


class DatabaseAvailabilityMiddleware:
    """Return a bounded service-unavailable response for database outages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except OperationalError:
            # Do not log exception details: drivers may include connection
            # information or query context. The fixed message is sufficient.
            logger.warning("Application database is unavailable; request returned 503.")
            response = HttpResponse(
                "The workspace is temporarily unavailable. Please try again shortly.",
                status=503,
                content_type="text/plain; charset=utf-8",
            )
            response["Retry-After"] = "5"
            return response
