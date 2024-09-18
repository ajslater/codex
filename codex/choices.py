"""Frontend Choices, Defaults and Messages."""
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
BROWSER_TOP_GROUP_CHOICES = MappingProxyType(
    {
        "a": "Story Arcs",
        "c": "Issues",
        "f": "Folders",
        "i": "Imprints",
        "p": "Publishers",
        "s": "Series",
        "v": "Volumes",
    },
)

BROWSER_CHOICES = MappingProxyType(
    {
        "bookmarkFilter": BROWSER_BOOKMARK_FILTER_CHOICES,
        "orderBy": BROWSER_ORDER_BY_CHOICES,
        "topGroup": BROWSER_TOP_GROUP_CHOICES,
        "vuetifyNullValue": -1,
        "groupNames": {
            "p": "Publishers",
            "i": "Imprints",
            "s": "Series",
            "v": "Volumes",
            "c": "Issues",
            "f": "Folders",
            "a": "Story Arcs",
        },
        "identifierTypes": {
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
        "fitTo": MappingProxyType(
            {
                "H": "Fit to Height",
                "O": "Original Size",
                "S": "Fit to Screen",
                "W": "Fit to Width",
            }
        ),
        "readingDirection": MappingProxyType(
            {
                "btt": "Bottom to Top",
                "ltr": "Left to Right",
                "rtl": "Right to Left",
                "ttb": "Top to Bottom",
            }
        ),
    }
)
DEFAULT_BROWSER_ROUTE = MappingProxyType({"group": "r", "page": 1, "pks": ()})
_DEFAULT_BROWSER_BREADCRUMBS = (DEFAULT_BROWSER_ROUTE,)
_DEFAULT_SHOW = MappingProxyType({"i": False, "p": True, "s": True, "v": False})
BROWSER_DEFAULTS = MappingProxyType(
    {
        "bookmarkFilter": "",
        "breadcrumbs": _DEFAULT_BROWSER_BREADCRUMBS,
        "customCovers": True,
        "dynamicCovers": True,
        "orderBy": "sort_name",
        "orderReverse": False,
        "q": "",
        "searchResultsLimit": 100,
        "show": _DEFAULT_SHOW,
        "topGroup": "p",
        "twentyFourHourTime": False,
    }
)
READER_DEFAULTS = MappingProxyType(
    {
        "finishOnLastPage": True,
        "fitTo": "S",
        "readingDirection": "ltr",
        "readRtlInReverse": False,
        "twoPages": False,
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
ADMIN_TASKS = MappingProxyType(
    {
        "tasks": (
            "adopt_folders",
            "cleanup_bookmarks",
            "cleanup_covers",
            "cleanup_db_custom_covers",
            "cleanup_fks",
            "cleanup_sessions",
            "codex_latest_version",
            "codex_restart",
            "codex_shutdown",
            "codex_update",
            "create_all_comic_covers",
            "db_backup",
            "db_foreign_key_check",
            "db_fts_integrity_check",
            "db_fts_rebuild",
            "db_integrity_check_long",
            "db_integrity_check_quick",
            "db_vacuum",
            "force_update_all_failed_imports",
            "force_update_groups",
            "janitor_nightly",
            "librarian_clear_status",
            "notify_librarian_status",
            "notify_library_changed",
            "poll",
            "poll_force",
            "purge_comic_covers",
            "search_index_abort",
            "search_index_clear",
            "search_index_optimize",
            "search_index_rebuild",
            "search_index_remove_stale",
            "search_index_update",
            "watchdog_sync",
        )
    }
)
WEBSOCKET_MESSAGES = MappingProxyType(
    {
        "messages": (
            "FAILED_IMPORTS",
            "LIBRARY_CHANGED",
            "LIBRARIAN_STATUS",
        )
    }
)
DUMMY_NULL_NAME = "_none_"
