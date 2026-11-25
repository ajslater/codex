"""Browser consts."""

BROWSER_FILTER_KEYS = (
    "age_rating_metron",
    "age_rating_tagged",
    "characters",
    "community_rating",
    "country",
    "credits",
    "decade",
    "file_type",
    "genres",
    "identifier_source",
    "language",
    "locations",
    "monochrome",
    "original_format",
    "reading_direction",
    "reading_list_kind",
    "reading_lists",
    "reprints",
    "series_end_year",
    "series_groups",
    "series_start_year",
    "series_status",
    "stories",
    "tagger",
    "tags",
    "teams",
    "universes",
    "year",
)
# The filters setting that names the filters set to match all ticked
# values. Not a filter of comics, so not in ``BROWSER_FILTER_KEYS``.
MATCH_ALL_KEY = "match_all"
