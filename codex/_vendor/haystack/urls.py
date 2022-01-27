from django.urls import path

from codex._vendor.haystack.views import SearchView

urlpatterns = [path("", SearchView(), name="haystack_search")]
