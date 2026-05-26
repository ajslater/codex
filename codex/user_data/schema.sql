-- User-data sidecar schema.
--
-- Every table is denormalized: foreign keys to volatile main-DB rows are
-- replaced with stable string identifiers (usernames, comic paths,
-- group name-chains, tag names) at write time. The sidecar has no
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

-- target is the polymorphic (group_char, identifier) pair.
-- identifier_json is a JSON-encoded name-chain tuple (see identifiers.py).
CREATE TABLE IF NOT EXISTS favorites (
    username TEXT NOT NULL,
    group_char TEXT NOT NULL,
    identifier_json TEXT NOT NULL,
    updated_at TEXT,
    PRIMARY KEY (username, group_char, identifier_json)
);

-- Per-user, per-client browser settings rows.
-- Anonymous-session rows are skipped (username IS NULL is never inserted).
CREATE TABLE IF NOT EXISTS settings_browser (
    username TEXT NOT NULL,
    client TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    top_group TEXT NOT NULL DEFAULT '',
    order_by TEXT NOT NULL DEFAULT '',
    order_reverse INTEGER NOT NULL DEFAULT 0,
    order_extra_keys TEXT NOT NULL DEFAULT '[]',
    search TEXT NOT NULL DEFAULT '',
    custom_covers INTEGER NOT NULL DEFAULT 1,
    dynamic_covers INTEGER NOT NULL DEFAULT 1,
    twenty_four_hour_time INTEGER NOT NULL DEFAULT 0,
    always_show_filename INTEGER NOT NULL DEFAULT 0,
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
-- tag table (see identifiers.py).
CREATE TABLE IF NOT EXISTS settings_filters (
    username TEXT NOT NULL,
    client TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    bookmark TEXT NOT NULL DEFAULT '',
    favorite INTEGER NOT NULL DEFAULT 0,
    age_rating_metron TEXT NOT NULL DEFAULT '[]',
    age_rating_tagged TEXT NOT NULL DEFAULT '[]',
    characters TEXT NOT NULL DEFAULT '[]',
    country TEXT NOT NULL DEFAULT '[]',
    credits TEXT NOT NULL DEFAULT '[]',
    critical_rating TEXT NOT NULL DEFAULT '[]',
    decade TEXT NOT NULL DEFAULT '[]',
    file_type TEXT NOT NULL DEFAULT '[]',
    genres TEXT NOT NULL DEFAULT '[]',
    identifier_source TEXT NOT NULL DEFAULT '[]',
    language TEXT NOT NULL DEFAULT '[]',
    locations TEXT NOT NULL DEFAULT '[]',
    monochrome TEXT NOT NULL DEFAULT '[]',
    original_format TEXT NOT NULL DEFAULT '[]',
    reading_direction TEXT NOT NULL DEFAULT '[]',
    series_groups TEXT NOT NULL DEFAULT '[]',
    stories TEXT NOT NULL DEFAULT '[]',
    story_arcs TEXT NOT NULL DEFAULT '[]',
    tagger TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    teams TEXT NOT NULL DEFAULT '[]',
    universes TEXT NOT NULL DEFAULT '[]',
    year TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (username, client, name)
);

-- 1:1 with settings_browser. pks_json is a JSON list of identifier
-- tuples (one per group, e.g. ["FooPub", "BarComics", "Baz Patrol"] for
-- a Series row).
CREATE TABLE IF NOT EXISTS settings_last_route (
    username TEXT NOT NULL,
    client TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    group_char TEXT NOT NULL DEFAULT 'r',
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
    prompt_timeout_seconds INTEGER NOT NULL DEFAULT 3600,
    metron_user TEXT NOT NULL DEFAULT '',
    metron_password TEXT NOT NULL DEFAULT '',
    metron_url TEXT NOT NULL DEFAULT '',
    comicvine_key TEXT NOT NULL DEFAULT '',
    comicvine_url TEXT NOT NULL DEFAULT '',
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
