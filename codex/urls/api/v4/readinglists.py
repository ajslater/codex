"""codex:api:v4:reading_lists URL Configuration."""

from django.urls import path
from django.views.decorators.cache import never_cache

from codex.views.readinglists.entries import (
    ReadingListAcceptView,
    ReadingListCandidatesView,
    ReadingListEntriesView,
    ReadingListEntryView,
    ReadingListRemoveView,
    ReadingListReorderView,
)
from codex.views.readinglists.lists import (
    ReadingListContinueView,
    ReadingListDetailView,
    ReadingListDuplicateView,
    ReadingListExportView,
    ReadingListsView,
)
from codex.views.readinglists.selection import ReadingListAddView

app_name = "reading_lists"
urlpatterns = [
    path("", never_cache(ReadingListsView.as_view()), name="list"),
    path("<int:pk>", never_cache(ReadingListDetailView.as_view()), name="detail"),
    path(
        "<int:pk>/duplicate",
        never_cache(ReadingListDuplicateView.as_view()),
        name="duplicate",
    ),
    path(
        "<int:pk>/continue",
        never_cache(ReadingListContinueView.as_view()),
        name="continue",
    ),
    path(
        "<int:pk>/export", never_cache(ReadingListExportView.as_view()), name="export"
    ),
    path(
        "<int:pk>/entries",
        never_cache(ReadingListEntriesView.as_view()),
        name="entries",
    ),
    path("<int:pk>/add", never_cache(ReadingListAddView.as_view()), name="add"),
    path(
        "<int:pk>/remove", never_cache(ReadingListRemoveView.as_view()), name="remove"
    ),
    path(
        "<int:pk>/entries/reorder",
        never_cache(ReadingListReorderView.as_view()),
        name="reorder",
    ),
    path(
        "<int:pk>/entries/accept",
        never_cache(ReadingListAcceptView.as_view()),
        name="accept",
    ),
    path(
        "<int:pk>/entries/<int:entry_pk>",
        never_cache(ReadingListEntryView.as_view()),
        name="entry",
    ),
    path(
        "<int:pk>/entries/<int:entry_pk>/candidates",
        never_cache(ReadingListCandidatesView.as_view()),
        name="candidates",
    ),
]
