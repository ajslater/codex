"""codex:opds:v1 URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_page

from codex.urls.const import COMMON_TIMEOUT
from codex.views.opds.authentication_v1 import OPDSAuthentication1View

app_name = "authentication"


urlpatterns = [
    path(
        "v1",
        cache_page(COMMON_TIMEOUT)(OPDSAuthentication1View.as_view()),
        name="v1",
    ),
]
