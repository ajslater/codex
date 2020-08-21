"""Export comicbox metadata to comicapi metadata."""
COMICAPI_SCHEMA = {
    "series": "series",
    "issue": "issue",
    "title": "title",
    "publisher": "publisher",
    "month": "month",
    "year": "year",
    "day": "day",
    "issueCount": "issue_count",
    "volume": "volume",
    "genre": "genre",
    "language": "language",
    "comments": "comments",
    "volumeCount": "volume_count",
    "criticalRating": "criticual_rating",
    "country": "country",
    "alternateSeries": "alternate_series",
    "alternateCount": "alternate_issue_count",
    "alternateNumber": "alternate_issue",
    "imprint": "imprint",
    "notes": "notes",
    "webLink": "web",
    "format": "format",
    "manga": "manga",
    "blackAndWhite": "black_and_white",
    "pageCount": "page_count",
    "maturityRating": "maturity_rating",
    "storyArc": "story_arc",
    "seriesGroup": "series_group",
    "scanInfo": "scan_info",
    "characters": "characters",
    "teams": "teams",
    "locations": "locations",
    "credits": "credits",
    "tags": "tags",
    "pages": "pages",
    "price": "price",
    "isVersionOf": "alternate_series",
    "rights": "rights",
    "identifier": "identifier",
    "lastMark": "lastMark",
    "coverImage": "cover_image",
}


def export(metadata, cls=None):
    """
    Export metadata to comicapi metadata.

    Optionally overlay that data onto a custom class.
    """
    if cls is None:
        cls = object
    gmd = cls()
    for attr, key in COMICAPI_SCHEMA.items():
        val = metadata.get(key)
        setattr(gmd, attr, val)
    return gmd
