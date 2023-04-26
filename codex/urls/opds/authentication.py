"""codex:opds:v1 URL Configuration."""
from django.urls import path
from django.views.decorators.cache import cache_page

from codex.views.opds.authentication_v1 import OPDSAuthentication1View

TIMEOUT = 60 * 60

app_name = "authentication"


urlpatterns = [
    path(
        "/v1",
        cache_page(TIMEOUT)(OPDSAuthentication1View.as_view()),
        name="v1",
    ),
]
