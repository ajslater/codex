"""
KOReader kosync URLs.

Paths match koreader-sync-server's, without trailing slashes, because the
kosync plugin appends them to the server URL the user types.
"""

from django.urls import path

from codex.views.koreader.progress import (
    KOSyncProgressGetView,
    KOSyncProgressPutView,
)
from codex.views.koreader.users import (
    KOSyncHealthcheckView,
    KOSyncUsersAuthView,
    KOSyncUsersCreateView,
)

app_name = "koreader"

urlpatterns = [
    path("users/auth", KOSyncUsersAuthView.as_view(), name="users_auth"),
    path("users/create", KOSyncUsersCreateView.as_view(), name="users_create"),
    path("syncs/progress", KOSyncProgressPutView.as_view(), name="progress_put"),
    path(
        "syncs/progress/<str:document>",
        KOSyncProgressGetView.as_view(),
        name="progress_get",
    ),
    path("healthcheck", KOSyncHealthcheckView.as_view(), name="healthcheck"),
]
