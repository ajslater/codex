"""Admin Jobs: task-to-status mapping for the combined Jobs tab."""

from types import MappingProxyType

# All importer sub-status codes (triggered by poll/import tasks).
_IMPORTER_STATUSES = (
    "IRT",
    "IAT",
    "IQT",
    "IQC",
    "IQL",
    "IQV",
    "ICT",
    "IUT",
    "ICC",
    "IUC",
    "ICV",
    "IUV",
    "ILT",
    "ILV",
    "IMF",
    "IMC",
    "IMV",
    "IRF",
    "IRC",
    "IRV",
    "ISU",
    "ISC",
    "IFQ",
    "IFU",
    "IFC",
    "IFD",
)

_POLL_STATUSES = ("WPO", *_IMPORTER_STATUSES, "IGU")

_SEARCH_SYNC_STATUSES = ("SSU", "SSC")

_JANITOR_NIGHTLY_STATUSES = (
    "JLV",
    "JAF",
    "IMF",
    "JIF",
    "JID",
    "JIS",
    "JCT",
    "JRV",
    "JRS",
    "JRB",
    "SIR",
    "SSU",
    "SSC",
    "SIO",
    "JDO",
    "JDB",
    "CFO",
    "CRC",
)

# Maps task value to a dict of metadata for the Jobs tab.
# "statuses": tuple of LibrarianStatus.status_type codes this task drives.
# "abort": optional task value that aborts this job.
# title and value are Vuetify format for easier loading in the frontend.
ADMIN_JOBS: MappingProxyType[str, tuple[dict, ...]] = MappingProxyType(
    {
        "ADMIN_JOBS": (
            {
                "title": "Libraries",
                "jobs": (
                    {
                        "value": "poll",
                        "title": "Update Libraries",
                        "statuses": _POLL_STATUSES,
                        "abort": "import_abort",
                        "variants": (
                            {
                                "value": "poll",
                                "title": "Poll",
                                "desc": ("Update Libraries if changes detected"),
                            },
                            {
                                "value": "poll_force",
                                "title": "Force Update",
                                "desc": ("Forcibly update all comics in all libraries"),
                                "confirm": "This can take a long time",
                            },
                            {
                                "value": "force_update_all_failed_imports",
                                "title": "Failed Imports",
                                "desc": (
                                    "Forcibly update all failed imports in"
                                    " all libraries"
                                ),
                                "confirm": "This can take a long time",
                            },
                        ),
                    },
                    {
                        "value": "watcher_restart",
                        "title": "Update Watcher with DB",
                        "desc": (
                            "Ensure the file Watcher is updated per database"
                            " preferences for each library"
                        ),
                        "statuses": (),
                    },
                ),
            },
            {
                "title": "Covers",
                "jobs": (
                    {
                        "value": "purge_comic_covers",
                        "title": "Remove Comic Covers",
                        "desc": "from every library",
                        "confirm": "Are you sure?",
                        "statuses": ("CRC",),
                    },
                    {
                        "value": "create_all_comic_covers",
                        "title": "Create All Comic Covers",
                        "desc": (
                            "Pre-generate covers for every comic in every"
                            " library and all custom covers"
                        ),
                        "confirm": "Are you sure?",
                        "statuses": ("CCC",),
                    },
                    {
                        "value": "force_update_groups",
                        "title": "Update Group Timestamps",
                        "desc": (
                            "Force the update of group timestamps. Will bust"
                            " the browser cache for browser views and covers."
                        ),
                        "statuses": ("IGU",),
                    },
                ),
            },
            {
                "title": "Search Index",
                "jobs": (
                    {
                        "value": "search_index_update",
                        "title": "Sync Search Index",
                        "statuses": ("SIX", *_SEARCH_SYNC_STATUSES),
                        "abort": "search_index_abort",
                        "variants": (
                            {
                                "value": "search_index_update",
                                "title": "Sync Search Index",
                                "desc": "with recently changed comics.",
                                "confirm": "This can take a long time",
                            },
                            {
                                "value": "search_index_rebuild",
                                "title": "Rebuild Search Index Using Sync",
                                "desc": (
                                    "Delete and rebuild the search index"
                                    " from scratch using the syncer."
                                ),
                                "confirm": "This can take a long time",
                            },
                        ),
                    },
                    {
                        "value": "search_index_optimize",
                        "title": "Optimize Search Index",
                        "desc": (
                            "Merge Search Index for optimal lookup time. Runs nightly."
                        ),
                        "statuses": ("SIO",),
                    },
                    {
                        "value": "search_index_remove_stale",
                        "title": "Clean Stale Index Entries",
                        "desc": (
                            "Clean search index entries that are no longer in"
                            " the library."
                        ),
                        "statuses": ("SIR",),
                    },
                    {
                        "value": "search_index_clear",
                        "title": "Clear Search Index",
                        "desc": "of all entries",
                        "confirm": (
                            "Are you sure? Resyncing the search index can take a while."
                        ),
                        "statuses": ("SIX",),
                    },
                    {
                        "value": "db_fts_integrity_check",
                        "title": "Integrity Check Search Index",
                        "desc": ("Repairs Search Index on failure. Runs nightly"),
                        "statuses": ("JIS",),
                    },
                    {
                        "value": "db_fts_rebuild",
                        "title": "Repair Search Index",
                        "desc": (
                            "Probably faster than Rebuild if the integrity check fails."
                        ),
                        "statuses": ("JSR",),
                    },
                ),
            },
            {
                "title": "Database",
                "jobs": (
                    {
                        "value": "db_vacuum",
                        "title": "Optimize & Compact Database",
                        "desc": (
                            "Run the sqlite3 OPTIMIZE and VACUUM pragmas. Runs nightly"
                        ),
                        "statuses": ("JDO",),
                    },
                    {
                        "value": "db_backup",
                        "title": "Backup Database",
                        "desc": "Runs nightly",
                        "statuses": ("JDB",),
                    },
                    {
                        "value": "db_foreign_key_check",
                        "title": "Remove Illegal Foreign Keys",
                        "desc": (
                            "Check for and remove illegal foreign keys. Mark"
                            " affected comics for update. Runs nightly."
                        ),
                        "statuses": ("JIF",),
                    },
                    {
                        "value": "db_integrity_check",
                        "title": "Check Database Integrity",
                        "desc": "Check logs for results. Runs nightly.",
                        "confirm": (
                            "Can take a while on large databases, Are you sure?"
                        ),
                        "statuses": ("JID",),
                    },
                ),
            },
            {
                "title": "Codex Software",
                "jobs": (
                    {
                        "value": "codex_latest_version",
                        "title": "Check for Codex Latest Version",
                        "desc": "Check PyPi for the latest version of Codex",
                        "statuses": ("JLV",),
                    },
                    {
                        "value": "codex_update",
                        "title": "Update Codex",
                        "desc": ("If Codex updates to a new version, it will restart"),
                        "confirm": "Are you sure?",
                        "statuses": ("JCU",),
                    },
                    {
                        "value": "codex_restart",
                        "title": "Restart Codex Server",
                        "desc": "Immediately",
                        "confirm": "Are you sure?",
                        "statuses": ("RCR",),
                    },
                    {
                        "value": "codex_shutdown",
                        "title": "Shutdown Codex Server",
                        "desc": "Immediately",
                        "confirm": "Are you sure?",
                        "statuses": ("RCS",),
                    },
                ),
            },
            {
                "title": "Cleanup",
                "abort": "cleanup_abort",
                "jobs": (
                    {
                        "value": "janitor_nightly",
                        "title": "Run Nightly Maintenance",
                        "desc": (
                            "Runs several cleanup, index, and database tasks"
                            " that also run nightly."
                        ),
                        "confirm": ("Launches several tasks that run nightly anyway."),
                        "statuses": _JANITOR_NIGHTLY_STATUSES,
                    },
                    {
                        "value": "cleanup_fks",
                        "title": "Remove Orphan Tags",
                        "desc": (
                            "After deleting comics, unused linked objects"
                            " remain in case new comics use them."
                            " Runs nightly."
                        ),
                        "statuses": ("JCT",),
                    },
                    {
                        "value": "cleanup_db_custom_covers",
                        "title": "Remove Orphan Database Custom Covers",
                        "desc": (
                            "Remove Custom Covers from the db that no longer"
                            " represent custom cover images on disk."
                            " Runs nightly."
                        ),
                        "statuses": ("JRV",),
                    },
                    {
                        "value": "cleanup_sessions",
                        "title": "Cleanup Sessions",
                        "desc": ("Remove corrupt and expired sessions. Runs nightly."),
                        "statuses": ("JRS",),
                    },
                    {
                        "value": "cleanup_covers",
                        "title": "Remove Orphan Cover Thumbnails",
                        "desc": (
                            "no longer have source comics or custom images."
                            " Runs nightly."
                        ),
                        "statuses": ("CFO", "CRC"),
                    },
                    {
                        "value": "cleanup_bookmarks",
                        "title": "Remove Orphan Bookmarks",
                        "desc": ("Owned by no session or user. Runs nightly."),
                        "statuses": ("JRB",),
                    },
                    {
                        "value": "adopt_folders",
                        "title": "Adopt Orphan Folders",
                        "desc": (
                            "Move orphaned folders from the top of the folder"
                            " tree to under their correct parent. Runs"
                            " nightly and at startup."
                        ),
                        "statuses": ("JAF",),
                    },
                    {
                        "value": "librarian_clear_status",
                        "title": "Clear Librarian Statuses",
                        "desc": "Mark all Librarian tasks finished.",
                        "statuses": (),
                    },
                ),
            },
            {
                "title": "Notify",
                "jobs": (
                    {
                        "value": "notify_admin_flags_changed",
                        "title": "Admin Flags Changed",
                        "desc": ("Notify all users that admin flags have changed."),
                        "statuses": (),
                    },
                    {
                        "value": "notify_bookmark_changed",
                        "title": "Bookmark Changed",
                        "desc": ("Notify only your user that a bookmark changed."),
                        "statuses": (),
                    },
                    {
                        "value": "notify_covers_changed",
                        "title": "Covers Changed",
                        "desc": ("Notify all users that covers have changed."),
                        "statuses": (),
                    },
                    {
                        "value": "notify_failed_imports_changed",
                        "title": "Failed Imports Changed",
                        "desc": ("Notify admin users that failed imports have changed"),
                        "statuses": (),
                    },
                    {
                        "value": "notify_groups_changed",
                        "title": "Groups Changed",
                        "desc": ("Notify all users that ACL groups have changed."),
                        "statuses": (),
                    },
                    {
                        "value": "notify_library_changed",
                        "title": "Library Changed",
                        "desc": ("Notify all users libraries have changed."),
                        "statuses": (),
                    },
                    {
                        "value": "notify_librarian_status",
                        "title": "Librarian Status",
                        "desc": (
                            "Notify admin users that a librarian job status changed."
                        ),
                        "statuses": (),
                    },
                    {
                        "value": "notify_users_changed",
                        "title": "Users Changed",
                        "desc": (
                            "Notify one user that their users changed or all"
                            " users if a user was deleted."
                        ),
                        "statuses": (),
                    },
                ),
            },
        ),
    }
)
