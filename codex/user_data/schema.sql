-- User-data sidecar schema.
--
-- Every table is denormalized: foreign keys to volatile main-DB rows are
-- replaced with stable string identifiers (usernames, comic paths,
-- collection name-chains, tag names) at write time. The sidecar has no
-- foreign keys of its own — that's the point. It must survive the main
-- DB being deleted and rebuilt from a filesystem scan.

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY
);

-- Django auth.User + UserAuth merged (OneToOne in main DB).
CREATE TABLE IF NOT EXISTS users (
    username TEXT NOT NULL PRIMARY KEY,
    password TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    is_staff INTEGER NOT NULL DEFAULT 0,
    is_superuser INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    date_joined TEXT,
    last_login TEXT,
    age_rating_metron_name TEXT,
    updated_at TEXT
);

-- Django auth.Group + GroupAuth merged (OneToOne in main DB).
CREATE TABLE IF NOT EXISTS groups (
    name TEXT NOT NULL PRIMARY KEY,
    permissions TEXT NOT NULL DEFAULT '[]',  -- JSON list of "app_label.codename"
    exclude INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT
);

-- M2M: User.groups
CREATE TABLE IF NOT EXISTS user_groups (
    username TEXT NOT NULL,
    group_name TEXT NOT NULL,
    PRIMARY KEY (username, group_name)
);

CREATE TABLE IF NOT EXISTS libraries (
    path TEXT NOT NULL PRIMARY KEY,
    events INTEGER NOT NULL DEFAULT 1,
    poll INTEGER NOT NULL DEFAULT 1,
    poll_every TEXT,                              -- ISO 8601 duration
    last_poll TEXT,
    updated_at TEXT
);

-- M2M: Library.groups
CREATE TABLE IF NOT EXISTS library_groups (
    library_path TEXT NOT NULL,
    group_name TEXT NOT NULL,
    PRIMARY KEY (library_path, group_name)
);

CREATE TABLE IF NOT EXISTS bookmarks (
    username TEXT NOT NULL,
    comic_path TEXT NOT NULL,
    page INTEGER,
    finished INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT,
    PRIMARY KEY (username, comic_path)
);

-- Reading lists a person made, imported or edited, keyed by the list's
-- UUID, which survives a restore. ``username`` is empty for a global list.
-- A list that only mirrors its story-arc tags is not stored: the tag sync
-- rebuilds it.
CREATE TABLE IF NOT EXISTS reading_lists (
    uuid TEXT NOT NULL PRIMARY KEY,
    username TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    list_notes TEXT NOT NULL DEFAULT '',
    list_type TEXT NOT NULL DEFAULT '',
    start_year INTEGER,
    end_year INTEGER,
    edited_fields TEXT NOT NULL DEFAULT '[]',
    order_locked INTEGER NOT NULL DEFAULT 0,
    extra TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT
);

-- A list's sources. ``document`` is the comicbox list as fetched or
-- uploaded, as JSON; a tags source has none, its arc ``ref`` is enough.
CREATE TABLE IF NOT EXISTS reading_list_sources (
    list_uuid TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref TEXT NOT NULL,
    revision TEXT NOT NULL DEFAULT '',
    attribution_source TEXT NOT NULL DEFAULT '',
    attribution_url TEXT NOT NULL DEFAULT '',
    rank INTEGER NOT NULL DEFAULT 0,
    ordered INTEGER NOT NULL DEFAULT 1,
    document TEXT,
    fetched_at TEXT,
    -- A collection item's collection and placement; its ``ref`` and
    -- ``document`` name it by identity (see identifiers.py).
    collection TEXT NOT NULL DEFAULT '',
    position INTEGER,
    PRIMARY KEY (list_uuid, kind, ref)
);

-- A list's entries in order, with every hand edit. The comic is its path;
-- ``sources`` names the entry's sources as [kind, ref] pairs.
CREATE TABLE IF NOT EXISTS reading_list_entries (
    list_uuid TEXT NOT NULL,
    position INTEGER NOT NULL,
    comic_path TEXT,
    reference TEXT NOT NULL DEFAULT '{}',
    series_name TEXT NOT NULL DEFAULT '',
    issue TEXT NOT NULL DEFAULT '',
    year INTEGER,
    match_tier TEXT NOT NULL DEFAULT '',
    needs_review INTEGER NOT NULL DEFAULT 0,
    ignored INTEGER NOT NULL DEFAULT 0,
    manual INTEGER NOT NULL DEFAULT 0,
    entry_type TEXT NOT NULL DEFAULT '',
    sources TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (list_uuid, position)
);

-- A saved answer "this list series is that library series", the series by
-- its name chain (see identifiers.py).
CREATE TABLE IF NOT EXISTS reading_list_series_mappings (
    series_key TEXT NOT NULL,
    year INTEGER NOT NULL DEFAULT 0,
    series_json TEXT NOT NULL,
    PRIMARY KEY (series_key, year)
);

-- A user's API keys, as hashes only: the plain key is never stored, so a
-- backup can restore a key that still logs in without ever holding it.
-- Names are unique per user, so (username, name) is the stable key.
CREATE TABLE IF NOT EXISTS api_keys (
    username TEXT NOT NULL,
    name TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'device',
    prefix TEXT NOT NULL DEFAULT '',
    digest TEXT NOT NULL,
    kosync_digest TEXT NOT NULL DEFAULT '',
    created_at TEXT,
    last_used_at TEXT,
    PRIMARY KEY (username, name)
);

-- Per-user, per-client browser settings rows.
-- Anonymous-session rows are skipped (username IS NULL is never inserted).
CREATE TABLE IF NOT EXISTS settings_browser (
    username TEXT NOT NULL,
    client TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    top_collection TEXT NOT NULL DEFAULT '',
    order_by TEXT NOT NULL DEFAULT '',
    order_reverse INTEGER NOT NULL DEFAULT 0,
    order_extra_keys TEXT NOT NULL DEFAULT '[]',
    collection_order_memory TEXT NOT NULL DEFAULT '{}',
    search TEXT NOT NULL DEFAULT '',
    twenty_four_hour_time INTEGER NOT NULL DEFAULT 0,
    always_show_filename INTEGER NOT NULL DEFAULT 0,
    show_missing_issues INTEGER NOT NULL DEFAULT 1,
    view_mode TEXT NOT NULL DEFAULT '',
    table_columns TEXT NOT NULL DEFAULT '{}',
    table_cover_size TEXT NOT NULL DEFAULT '',
    show_p INTEGER NOT NULL DEFAULT 1,
    show_i INTEGER NOT NULL DEFAULT 0,
    show_s INTEGER NOT NULL DEFAULT 1,
    show_v INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT,
    PRIMARY KEY (username, client, name)
);

-- 1:1 with settings_browser, keyed on the same (username, client, name).
-- Lists of tag PKs in the main DB become JSON arrays of names here, per
-- tag table (see identifiers.py). ``shelves`` held the owner's shelf names
-- before shelves folded into reading lists; an older backup's restore reads
-- it as the names of the owner's lists, and new backups leave it empty.
CREATE TABLE IF NOT EXISTS settings_filters (
    username TEXT NOT NULL,
    client TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    bookmark TEXT NOT NULL DEFAULT '',
    reading_list_kind TEXT NOT NULL DEFAULT '[]',
    match_all TEXT NOT NULL DEFAULT '[]',
    shelves TEXT NOT NULL DEFAULT '[]',
    age_rating_metron TEXT NOT NULL DEFAULT '[]',
    age_rating_tagged TEXT NOT NULL DEFAULT '[]',
    characters TEXT NOT NULL DEFAULT '[]',
    community_rating TEXT NOT NULL DEFAULT '[]',
    country TEXT NOT NULL DEFAULT '[]',
    credits TEXT NOT NULL DEFAULT '[]',
    decade TEXT NOT NULL DEFAULT '[]',
    file_type TEXT NOT NULL DEFAULT '[]',
    genres TEXT NOT NULL DEFAULT '[]',
    identifier_source TEXT NOT NULL DEFAULT '[]',
    language TEXT NOT NULL DEFAULT '[]',
    locations TEXT NOT NULL DEFAULT '[]',
    monochrome TEXT NOT NULL DEFAULT '[]',
    original_format TEXT NOT NULL DEFAULT '[]',
    reading_direction TEXT NOT NULL DEFAULT '[]',
    reading_lists TEXT NOT NULL DEFAULT '[]',
    reprints TEXT NOT NULL DEFAULT '[]',
    series_end_year TEXT NOT NULL DEFAULT '[]',
    series_groups TEXT NOT NULL DEFAULT '[]',
    series_start_year TEXT NOT NULL DEFAULT '[]',
    series_status TEXT NOT NULL DEFAULT '[]',
    stories TEXT NOT NULL DEFAULT '[]',
    tagger TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    teams TEXT NOT NULL DEFAULT '[]',
    universes TEXT NOT NULL DEFAULT '[]',
    year TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (username, client, name)
);

-- 1:1 with settings_browser. pks_json is a JSON list of identifier
-- tuples (one per collection, e.g. ["FooPub", "BarComics", "Baz Patrol"] for
-- a Series row).
CREATE TABLE IF NOT EXISTS settings_last_route (
    username TEXT NOT NULL,
    client TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    collection TEXT NOT NULL DEFAULT 'root',
    pks_json TEXT NOT NULL DEFAULT '[]',
    page INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (username, client, name)
);

CREATE TABLE IF NOT EXISTS admin_flags (
    key TEXT NOT NULL PRIMARY KEY,
    on_flag INTEGER NOT NULL DEFAULT 1,
    value TEXT NOT NULL DEFAULT '',
    age_rating_metron_name TEXT,
    updated_at TEXT
);

-- ComicboxTaggingDefaults — singleton (pk=1 enforced by main model).
-- ``active_session_id`` / ``active_prompts`` used to live here but
-- moved to the Django cache. Sidecar backups from older codex
-- versions may still include those columns; the restore code drops
-- them silently because they are transient operational state, not
-- user data that needs to round-trip.
CREATE TABLE IF NOT EXISTS tagging_defaults (
    pk INTEGER NOT NULL PRIMARY KEY DEFAULT 1,
    default_formats TEXT NOT NULL DEFAULT '[]',
    delete_original INTEGER NOT NULL DEFAULT 0,
    default_match_mode TEXT NOT NULL DEFAULT 'auto',
    default_prompts_mode TEXT NOT NULL DEFAULT 'ask',
    default_sources TEXT NOT NULL DEFAULT '[]',
    default_effort TEXT NOT NULL DEFAULT '',
    merge_all_sources INTEGER NOT NULL DEFAULT 0,
    rename_files INTEGER NOT NULL DEFAULT 0,
    metron_key TEXT NOT NULL DEFAULT '',
    comicvine_key TEXT NOT NULL DEFAULT '',
    comicvine_url TEXT NOT NULL DEFAULT '',
    versedb_key TEXT NOT NULL DEFAULT '',
    updated_at TEXT
);

-- ``SettingsDefaults`` singleton: the site default browser + reader settings
-- new sessions are seeded with. ``table_columns`` is a JSON object keyed by
-- top collection.
CREATE TABLE IF NOT EXISTS settings_defaults (
    pk INTEGER NOT NULL PRIMARY KEY DEFAULT 1,
    top_collection TEXT NOT NULL DEFAULT 'publishers',
    show_publishers INTEGER NOT NULL DEFAULT 1,
    show_imprints INTEGER NOT NULL DEFAULT 0,
    show_series INTEGER NOT NULL DEFAULT 1,
    show_volumes INTEGER NOT NULL DEFAULT 0,
    order_by TEXT NOT NULL DEFAULT '',
    order_reverse INTEGER NOT NULL DEFAULT 0,
    view_mode TEXT NOT NULL DEFAULT 'cover',
    twenty_four_hour_time INTEGER NOT NULL DEFAULT 0,
    always_show_filename INTEGER NOT NULL DEFAULT 0,
    bookmark TEXT NOT NULL DEFAULT '',
    table_columns TEXT NOT NULL DEFAULT '{}',
    fit_to TEXT NOT NULL DEFAULT 'W',
    reading_direction TEXT NOT NULL DEFAULT 'ltr',
    two_pages INTEGER NOT NULL DEFAULT 0,
    page_transition INTEGER NOT NULL DEFAULT 1,
    cache_book INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT
);

-- ``Timestamp`` model. ``value`` (previously ``version``) holds the
-- last-known value for the keyed singleton; ``updated_at`` is the
-- last-touch marker.
CREATE TABLE IF NOT EXISTS timestamps (
    key TEXT NOT NULL PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TEXT
);
