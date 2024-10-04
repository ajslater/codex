"""Frontend Choices, Defaults and Messages."""

from collections.abc import Mapping
from types import MappingProxyType

BROWSER_BOOKMARK_FILTER_CHOICES = MappingProxyType(
    {
        "": "All",
        "IN_PROGRESS": "In Progress",
        "READ": "Read",
        "UNREAD": "Unread",
    },
)
BROWSER_ORDER_BY_CHOICES = MappingProxyType(
    {
        "age_rating": "Age Rating",
        "bookmark_updated_at": "Last Read",
        "community_rating": "Community Rating",
        "created_at": "Added Time",
        "critical_rating": "Critical Rating",
        "date": "Publish Date",
        "filename": "Filename",
        "page_count": "Page Count",
        "search_score": "Search Score",
        "size": "File Size",
        "sort_name": "Name",
        "story_arc_number": "Story Arc Number",
        "updated_at": "Updated Time",
    }
)
_GROUP_NAMES = {
    "p": "Publishers",
    "i": "Imprints",
    "s": "Series",
    "v": "Volumes",
}
BROWSER_TOP_GROUP_CHOICES = MappingProxyType(
    {
        **_GROUP_NAMES,
        "c": "Issues",
        "f": "Folders",
        "a": "Story Arcs",
    },
)
VUETIFY_NULL_CODE = -1
BROWSER_CHOICES = MappingProxyType(
    {
        "bookmark_filter": BROWSER_BOOKMARK_FILTER_CHOICES,
        "order_by": BROWSER_ORDER_BY_CHOICES,
        "top_group": BROWSER_TOP_GROUP_CHOICES,
        "vuetify_null_code": VUETIFY_NULL_CODE,
        "settings_group": {**_GROUP_NAMES},
        "identifier_types": {
            "comicvine": "Comic Vine",
            "comixology": "Comixology",
            "asin": "Amazon",
            "gtin": "GTIN",
            "isbn": "ISBN",
            "upc": "UPC",
        },
    }
)

READER_CHOICES = MappingProxyType(
    {
        "fit_to": MappingProxyType(
            {
                "H": "Fit to Height",
                "O": "Original Size",
                "S": "Fit to Screen",
                "W": "Fit to Width",
            }
        ),
        "reading_direction": MappingProxyType(
            {
                "btt": "Bottom to Top",
                "ltr": "Left to Right",
                "rtl": "Right to Left",
                "ttb": "Top to Bottom",
            }
        ),
    }
)
DEFAULT_BROWSER_ROUTE = MappingProxyType({"group": "r", "pks": (0,), "page": 1})
_DEFAULT_BROWSER_BREADCRUMBS = (DEFAULT_BROWSER_ROUTE,)
_DEFAULT_SHOW = MappingProxyType({"i": False, "p": True, "s": True, "v": False})
BROWSER_DEFAULTS = MappingProxyType(
    {
        "bookmark_filter": "",
        "breadcrumbs": _DEFAULT_BROWSER_BREADCRUMBS,
        "custom_covers": True,
        "dynamic_covers": True,
        "order_by": "sort_name",
        "order_reverse": False,
        "q": "",
        # "search_results_limit": 100,
        "show": _DEFAULT_SHOW,
        "top_group": "p",
        "twenty_four_hour_time": False,
    }
)
READER_DEFAULTS = MappingProxyType(
    {
        "finish_on_last_page": True,
        "fit_to": "S",
        "reading_direction": "ltr",
        "read_rtl_in_reverse": False,
        "two_pages": False,
    }
)

ADMIN_FLAG_CHOICES = MappingProxyType(
    {
        "AU": "Auto Update",
        "FV": "Folder View",
        "IM": "Import Metadata on Library Scan",
        "NU": "Non Users",
        "RG": "Registration",
        "ST": "Send Stats",
    }
)

ADMIN_STATUS_TITLES = MappingProxyType(
    {
        "CCC": "Create Covers",
        "CCD": "Remove Covers",
        "CFO": "Find Orphan Covers",
        "IAF": "Adopt Orphan Folders",
        "ICC": "Create Custom Covers",
        "ICD": "Delete Custom Covers",
        "ICL": "Link Custom Covers",
        "ICM": "Custom Covers Moved",
        "ICQ": "Discover Missing Custom Covers",
        "ICU": "Modify Custom Covers",
        "IDD": "Remove Folders",
        "IDM": "Move Folders",
        "IDU": "Modify Folders",
        "IFC": "Create Books",
        "IFD": "Remove Books",
        "IFI": "Record Failed Imports",
        "IFM": "Move Books",
        "IFU": "Modify Books",
        "IGU": "Update First Covers",
        "IMC": "Link Books to Tags",
        "IMQ": "Prepare Tags for Linking",
        "ITC": "Create Missing Tags",
        "ITQ": "Discover Missing Tags",
        "ITR": "Read Book Tags",
        "JCB": "Cleanup Orphan Bookmarks",
        "JCD": "Cleanup Custom Covers",
        "JCR": "Restart Codex",
        "JCS": "Stop Codex",
        "JCU": "Update Codex Software",
        "JDB": "Backup Database",
        "JDO": "Optimize Database",
        "JFC": "Search Index Integrity Check",
        "JFR": "Search Index Repair",
        "JIC": "Database Integrity Check",
        "JIF": "Database Foreign Key Check",
        "JLV": "Check Codex Latest Version",
        "JSD": "Cleanup Expired Sessions",
        "JTD": "Cleanup Stale Tags",
        "SIC": "Search Index Create",
        "SID": "Search Index Remove Stale Records",
        "SIO": "Search Index Optimize",
        "SIU": "Search Index Update",
        "SIX": "Search Index Clear",
        "WPO": "Poll Library",
    }
)

# Easier to store in vuetify format
ADMIN_TASK_GROUPS = MappingProxyType(
    {
        "tasks": (
            {
                "title": "Libraries",
                "tasks": [
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
                ],
            },
            {
                "title": "Covers",
                "tasks": [
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
                ],
            },
            {
                "title": "Search Index",
                "tasks": [
                    {
                        "value": "search_index_update",
                        "title": "Update Search Index",
                        "desc": "with recently changed comics",
                    },
                    {
                        "value": "search_index_optimize",
                        "title": "Optimize Search Index",
                        "desc": "Merge Search Index for optimal lookup time. Runs nightly.",
                    },
                    {
                        "value": "search_index_rebuild",
                        "title": "Rebuild Search Index",
                        "desc": "Delete and rebuild the search index from scratch",
                        "confirm": "This can take a long time",
                    },
                    {
                        "value": "search_index_remove_stale",
                        "title": "Remove Stale Index Entries",
                        "desc": "Remove search index entries that are no longer in the library.",
                    },
                    {
                        "value": "search_index_abort",
                        "title": "Abort Search Indexing",
                        "desc": "Aborts search index update and remove tasks.",
                    },
                    {
                        "value": "search_index_clear",
                        "title": "Clear Search Index",
                        "desc": "of all entries",
                    },
                    {
                        "value": "db_fts_integrity_check",
                        "title": "Integrity Check Search Index",
                        "desc": "Repairs Search Index on failure. Runs nightly",
                    },
                    {
                        "value": "db_fts_rebuild",
                        "title": "Repair Search Index",
                        "desc": "Probably faster than Rebuild if integrity check fails.",
                    },
                ],
            },
            {
                "title": "Database",
                "tasks": [
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
                ],
            },
            {
                "title": "Codex Software",
                "tasks": [
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
                ],
            },
            {
                "title": "Notify",
                "tasks": [
                    {
                        "value": "notify_library_changed",
                        "title": "Notify Library Changed ",
                        "desc": "Signal all clients that the libraries have changed and the browser should fetch new data.",
                    },
                    {
                        "value": "notify_librarian_status",
                        "title": "Notify Librarian Status",
                        "desc": "Signal Admin clients to fetch librarian status.",
                    },
                ],
            },
            {
                "title": "Cleanup",
                "tasks": [
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
                ],
            },
        )
    }
)


def _group_task_values(groups):
    """Extract values into sorted tuple."""
    values = []
    for group in groups["tasks"]:
        for item in group["tasks"]:
            values.append(item["value"])
    return tuple(sorted(values))


ADMIN_TASKS = _group_task_values(ADMIN_TASK_GROUPS)
WEBSOCKET_MESSAGES = MappingProxyType(
    {
        "messages": {
            "FAILED_IMPORTS": "FAILED_IMPORTS",
            "LIBRARY_CHANGED": "LIBRARY_CHANGED",
            "LIBRARIAN_STATUS": "LIBRARIAN_STATUS",
        }
    }
)
DUMMY_NULL_NAME = "_none_"


def mapping_to_dict(data):
    """Convert nested Mapping objects to dicts."""
    if isinstance(data, Mapping):
        return {key: mapping_to_dict(value) for key, value in data.items()}
    if isinstance(data, list | tuple | frozenset | set):
        return [mapping_to_dict(item) for item in data]
    return data
