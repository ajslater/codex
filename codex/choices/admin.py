"""Admin Choices."""

from types import MappingProxyType

from django.db.models.enums import TextChoices


class AdminFlagChoices(TextChoices):
    """Choices for Admin Flags."""

    AUTO_UPDATE = "AU"
    BANNER_TEXT = "BT"
    FOLDER_VIEW = "FV"
    IMPORT_METADATA = "IM"
    LAZY_IMPORT_METADATA = "LI"
    NON_USERS = "NU"
    REGISTRATION = "RG"
    SEND_TELEMETRY = "ST"


ADMIN_FLAG_CHOICES = MappingProxyType(
    {
        AdminFlagChoices.AUTO_UPDATE.value: "Auto Update",
        AdminFlagChoices.BANNER_TEXT.value: "Banner Text",
        AdminFlagChoices.FOLDER_VIEW.value: "Folder View",
        AdminFlagChoices.IMPORT_METADATA.value: "Import Metadata on Library Scan",
        AdminFlagChoices.LAZY_IMPORT_METADATA.value: "Import Metadata on Demand",
        AdminFlagChoices.NON_USERS.value: "Non Users",
        AdminFlagChoices.REGISTRATION.value: "Registration",
        AdminFlagChoices.SEND_TELEMETRY.value: "Send Stats",
    }
)


# Easier to store in vuetify format
ADMIN_TASK_GROUPS: MappingProxyType[
    str, tuple[dict[str, str | tuple[dict[str, str], ...]], ...]
] = MappingProxyType(
    {
        "tasks": (
            {
                "title": "Libraries",
                "tasks": (
                    {
                        "value": "poll",
                        "title": "Poll All Libraries",
                        "desc": "Update Libraries if changes detected",
                    },
                    {
                        "value": "poll_force",
                        "title": "Force Update All Libraries",
                        "desc": "Forcibly update all comics in all libraries",
                        "confirm": "This can take a long time",
                    },
                    {
                        "value": "force_update_all_failed_imports",
                        "title": "Update All Failed Imports",
                        "desc": "Forcibly update all failed imports in all libraries",
                        "confirm": "This can take a long time",
                    },
                    {
                        "value": "watchdog_sync",
                        "title": "Sync Watchdog with DB",
                        "desc": "Ensure the Watchdog file watcher is enabled per database preferences for each library",
                    },
                    {
                        "value": "import_abort",
                        "title": "Abort Running Import",
                        "desc": "Abort the current running import after the current import subtask is complete",
                    },
                ),
            },
            {
                "title": "Covers",
                "tasks": (
                    {
                        "value": "purge_comic_covers",
                        "title": "Remove Comic Covers",
                        "desc": "from every library",
                        "confirm": "Are you sure?",
                    },
                    {
                        "value": "create_all_comic_covers",
                        "title": "Create All Comic Covers",
                        "desc": "Pre-generate covers for every comic in every library and all custom covers",
                        "confirm": "Are you sure?",
                    },
                    {
                        "value": "force_update_groups",
                        "title": "Update Group Timestamps",
                        "desc": "Force the update of group timestamps. Will bust the browser cache for browser views and covers.",
                    },
                ),
            },
            {
                "title": "Search Index",
                "tasks": (
                    {
                        "value": "search_index_optimize",
                        "title": "Optimize Search Index",
                        "desc": "Merge Search Index for optimal lookup time. Runs nightly.",
                    },
                    {
                        "value": "search_index_remove_stale",
                        "title": "Clean Stale Index Entries",
                        "desc": "Clean search index entries that are no longer in the library.",
                    },
                    {
                        "value": "search_index_clear",
                        "title": "Clear Search Index",
                        "desc": "of all entries",
                        "confirm": "Are you sure? Resyncing the search index can take a while.",
                    },
                    {
                        "value": "db_fts_integrity_check",
                        "title": "Integrity Check Search Index",
                        "desc": "Repairs Search Index on failure. Runs nightly",
                    },
                    {
                        "value": "db_fts_rebuild",
                        "title": "Repair Search Index",
                        "desc": "Probably faster than Rebuild if the integrity check fails.",
                    },
                    {
                        "value": "search_index_abort",
                        "title": "Abort Search Index Sync",
                        "desc": "Aborts search index sync tasks.",
                    },
                    {
                        "value": "search_index_update",
                        "title": "Sync Search Index",
                        "desc": "with recently changed comics.",
                        "confirm": "This can take a long time",
                    },
                    {
                        "value": "search_index_rebuild",
                        "title": "Rebuild Search Index Using Sync.",
                        "desc": "Delete and rebuild the search index from scratch using the syncer.",
                        "confirm": "This can take a long time",
                    },
                ),
            },
            {
                "title": "Database",
                "tasks": (
                    {
                        "value": "db_vacuum",
                        "title": "Optimize & Compact Database",
                        "desc": "Run the sqlite3 OPTIMIZE and VACUUM pragmas. Runs nightly",
                    },
                    {
                        "value": "db_backup",
                        "title": "Backup Database",
                        "desc": "Runs nightly",
                    },
                    {
                        "value": "db_foreign_key_check",
                        "title": "Remove Illegal Foreign Keys",
                        "desc": "Check for and remove illegal foreign keys. Mark affected comics for update. Runs nightly.",
                    },
                    {
                        "value": "db_integrity_check",
                        "title": "Check Database Integrity",
                        "desc": "Check logs for results. Runs nightly.",
                        "confirm": "Can take a while on large databases, Are you sure?",
                    },
                ),
            },
            {
                "title": "Codex Software",
                "tasks": (
                    {
                        "value": "codex_latest_version",
                        "title": "Check for Codex Latest Version",
                        "desc": "Check PyPi for the latest version of Codex",
                    },
                    {
                        "value": "codex_update",
                        "title": "Update Codex",
                        "desc": "If Codex updates to a new version, it will restart",
                        "confirm": "Are you sure?",
                    },
                    {
                        "value": "codex_restart",
                        "title": "Restart Codex Server",
                        "desc": "Immediately",
                        "confirm": "Are you sure?",
                    },
                    {
                        "value": "codex_shutdown",
                        "title": "Shutdown Codex Server",
                        "desc": "Immediately",
                        "confirm": "Are you sure?",
                    },
                ),
            },
            {
                "title": "Cleanup",
                "tasks": (
                    {
                        "value": "cleanup_fks",
                        "title": "Remove Orphan Tags",
                        "desc": "After deleting comics, unused linked objects remain in case new comics use them. Runs nightly.",
                    },
                    {
                        "value": "cleanup_db_custom_covers",
                        "title": "Remove Orphan Database Custom Covers",
                        "desc": "Remove Custom Covers from the db that no longer represent custom cover images on disk. Runs nightly.",
                    },
                    {
                        "value": "cleanup_sessions",
                        "title": "Cleanup Sessions",
                        "desc": "Remove corrupt and expired sessions. Runs nightly.",
                    },
                    {
                        "value": "cleanup_covers",
                        "title": "Remove Orphan Cover Thumbnails",
                        "desc": "no longer have source comics or custom images. Runs nightly.",
                    },
                    {
                        "value": "cleanup_bookmarks",
                        "title": "Remove Orphan Bookmarks",
                        "desc": "Owned by no session or user. Runs nightly.",
                    },
                    {
                        "value": "adopt_folders",
                        "title": "Adopt Orphan Folders",
                        "desc": "Move orphaned folders from the top of the folder tree to under their correct parent. Runs nightly and at startup.",
                    },
                    {
                        "value": "librarian_clear_status",
                        "title": "Clear Librarian Statuses",
                        "desc": "Mark all Librarian tasks finished.",
                    },
                    {
                        "value": "janitor_nightly",
                        "title": "Run Nightly Maintenance",
                        "desc": "Runs several tasks above that also run nightly.",
                        "confirm": "Launches several tasks that run nightly anyway.",
                    },
                ),
            },
            {
                "title": "Notify",
                "tasks": (
                    {
                        "value": "notify_admin_flags_changed",
                        "title": "Notify Admin Flags Changed",
                        "desc": "Notify all users that admin flags have changed.",
                    },
                    {
                        "value": "notify_bookmark_changed",
                        "title": "Notify Bookmark Changed",
                        "desc": "Notify only your user that a bookmark changed.",
                    },
                    {
                        "value": "notify_covers_changed",
                        "title": "Notify Covers Changed",
                        "desc": "Notify all users that covers have changed.",
                    },
                    {
                        "value": "notify_failed_imports_changed",
                        "title": "Notify Failed Imports Changed",
                        "desc": "Notify admin users that failed imports have changed",
                    },
                    {
                        "value": "notify_groups_changed",
                        "title": "Notify Groups Changed",
                        "desc": "Notify all users that ACL groups have changed.",
                    },
                    {
                        "value": "notify_library_changed",
                        "title": "Notify Library Changed ",
                        "desc": "Notify all users libraries have changed.",
                    },
                    {
                        "value": "notify_librarian_status",
                        "title": "Notify Librarian Status",
                        "desc": "Notify admin users that a librarian job status changed..",
                    },
                    {
                        "value": "notify_users_changed",
                        "title": "Notify Users Changed",
                        "desc": "Notify one user that their users changed or all users if a user was deleted.",
                    },
                ),
            },
        ),
    }
)
