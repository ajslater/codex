"""Admin stats serializers."""

from typing import Final

from rest_framework.serializers import (
    BooleanField,
    CharField,
    IntegerField,
    Serializer,
)

from codex.librarian.telemeter.count_stats import (
    IDENTIFIER_SOURCES,
    OTHER_IDENTIFIER_SOURCE,
)
from codex.serializers.fields import (
    CountDictField,
    SerializerChoicesField,
    StringListMultipleChoiceField,
)

FILE_TYPES_CHOICES: Final[tuple[str, ...]] = (
    "CBZ",
    "CBR",
    "CBT",
    "CB7",
    "PDF",
    "UNKNOWN",
)
# Identifier buckets are keyed "<source>:<id_type>". Requests select whole
# sources; the source vocabulary is comicbox's, plus the "other" catch-all
# the telemeter collapses unrecognized sources into.
IDENTIFIER_SOURCE_CHOICES: Final[tuple[str, ...]] = (
    *sorted(IDENTIFIER_SOURCES),
    OTHER_IDENTIFIER_SOURCE,
)


class StatsSystemSerializer(Serializer):
    """Platform System Information."""

    name = CharField(read_only=True, required=False)
    release = CharField(read_only=True, required=False)


class StatsPlatformSerializer(Serializer):
    """Platform Information."""

    docker = BooleanField(read_only=True)
    machine = CharField(read_only=True)
    cores = IntegerField(read_only=True)
    system = StatsSystemSerializer(read_only=True)
    python_version = CharField(read_only=True)
    codex_version = CharField(read_only=True)


class StatsConfigSerializer(Serializer):
    """Config Information."""

    library_count = IntegerField(required=False, read_only=True)
    session_count = IntegerField(required=False, read_only=True)
    user_anonymous_count = IntegerField(required=False, read_only=True)
    user_registered_count = IntegerField(required=False, read_only=True)
    auth_group_count = IntegerField(required=False, read_only=True)
    library_read_only_count = IntegerField(required=False, read_only=True)
    library_poll_count = IntegerField(required=False, read_only=True)
    library_events_count = IntegerField(required=False, read_only=True)
    library_group_acl_count = IntegerField(required=False, read_only=True)
    custom_cover_count = IntegerField(required=False, read_only=True)
    custom_cover_uploaded_count = IntegerField(required=False, read_only=True)
    custom_cover_dir_count = IntegerField(required=False, read_only=True)
    failed_import_count = IntegerField(required=False, read_only=True)
    # Only for api
    api_key = CharField(read_only=True, required=False)


class StatsSessionsSerializer(Serializer):
    """Session Settings."""

    top_collection = CountDictField(required=False, read_only=True)
    order_by = CountDictField(required=False, read_only=True)
    dynamic_covers = CountDictField(required=False, read_only=True)
    finish_on_last_page = CountDictField(required=False, read_only=True)
    fit_to = CountDictField(required=False, read_only=True)
    reading_direction = CountDictField(required=False, read_only=True)
    view_mode = CountDictField(required=False, read_only=True)
    table_cover_size = CountDictField(required=False, read_only=True)
    custom_covers = CountDictField(required=False, read_only=True)
    multi_sort_count = IntegerField(required=False, read_only=True)


class StatsCollectionSerializer(Serializer):
    """Collection Counts."""

    publisher_count = IntegerField(required=False, read_only=True)
    imprint_count = IntegerField(required=False, read_only=True)
    series_count = IntegerField(required=False, read_only=True)
    volume_count = IntegerField(required=False, read_only=True)
    issue_count = IntegerField(required=False, read_only=True)
    folder_count = IntegerField(required=False, read_only=True)
    story_arc_count = IntegerField(required=False, read_only=True)


class StatsComicMetadataSerializer(Serializer):
    """Metadata Counts."""

    age_rating_count = IntegerField(required=False, read_only=True)
    character_count = IntegerField(required=False, read_only=True)
    credit_count = IntegerField(required=False, read_only=True)
    credit_person_count = IntegerField(required=False, read_only=True)
    credit_role_count = IntegerField(required=False, read_only=True)
    country_count = IntegerField(required=False, read_only=True)
    genre_count = IntegerField(required=False, read_only=True)
    identifier_count = IntegerField(required=False, read_only=True)
    identifier_source_count = IntegerField(required=False, read_only=True)
    language_count = IntegerField(required=False, read_only=True)
    location_count = IntegerField(required=False, read_only=True)
    original_format_count = IntegerField(required=False, read_only=True)
    reprint_count = IntegerField(required=False, read_only=True)
    series_group_count = IntegerField(required=False, read_only=True)
    scan_info_count = IntegerField(required=False, read_only=True)
    story_arc_count = IntegerField(required=False)
    story_arc_number_count = IntegerField(required=False, read_only=True)
    story_count = IntegerField(required=False, read_only=True)
    tag_count = IntegerField(required=False, read_only=True)
    tagger_count = IntegerField(required=False, read_only=True)
    team_count = IntegerField(required=False, read_only=True)
    universe_count = IntegerField(required=False, read_only=True)
    comic_community_rating_count = IntegerField(required=False, read_only=True)
    comic_community_rating_vote_count = IntegerField(required=False, read_only=True)
    comic_alternative_issue_number_count = IntegerField(required=False, read_only=True)
    comic_metadata_imported_count = IntegerField(required=False, read_only=True)


class StatsUsageSerializer(Serializer):
    """Reader Engagement Counts."""

    bookmark_count = IntegerField(required=False, read_only=True)
    favorite_count = IntegerField(required=False, read_only=True)
    favorite_user_count = IntegerField(required=False, read_only=True)
    favorites = CountDictField(required=False, read_only=True)


class StatsAdminFlagsSerializer(Serializer):
    """
    Admin Flag Settings.

    Flags holding admin-authored text report only whether they are set.
    """

    auto_update = BooleanField(required=False, read_only=True)
    folder_view = BooleanField(required=False, read_only=True)
    import_metadata = BooleanField(required=False, read_only=True)
    lazy_import_metadata = BooleanField(required=False, read_only=True)
    non_users = BooleanField(required=False, read_only=True)
    registration = BooleanField(required=False, read_only=True)
    register_verification = BooleanField(required=False, read_only=True)
    send_telemetry = BooleanField(required=False, read_only=True)
    api_key_set = BooleanField(required=False, read_only=True)
    banner_text_set = BooleanField(required=False, read_only=True)
    browser_default_collection = CharField(required=False, read_only=True)
    browser_max_obj_per_page = IntegerField(required=False, read_only=True)
    custom_cover_max_upload_mb = IntegerField(required=False, read_only=True)
    age_rating_default = CharField(required=False, read_only=True, allow_blank=True)
    anonymous_user_age_rating = CharField(
        required=False, read_only=True, allow_blank=True
    )


class StatsTaggingSerializer(Serializer):
    """
    Online Tagging Defaults.

    Credentials and the Comic Vine url report only whether they are configured.
    """

    default_match_mode = CharField(required=False, read_only=True)
    default_prompts_mode = CharField(required=False, read_only=True)
    merge_all_sources = BooleanField(required=False, read_only=True)
    delete_original = BooleanField(required=False, read_only=True)
    rename_files = BooleanField(required=False, read_only=True)
    default_sources = CountDictField(required=False, read_only=True)
    default_format_count = IntegerField(required=False, read_only=True)
    has_metron_credentials = BooleanField(required=False, read_only=True)
    has_comicvine_credentials = BooleanField(required=False, read_only=True)
    comicvine_url_set = BooleanField(required=False, read_only=True)


class StatsAuthSerializer(Serializer):
    """
    Single Sign On & Access Restrictions.

    The provider name, urls, client id and secret are never reported.
    """

    oidc_enabled = BooleanField(required=False, read_only=True)
    oidc_create_users = BooleanField(required=False, read_only=True)
    oidc_link_by_email = BooleanField(required=False, read_only=True)
    oidc_sync_groups = BooleanField(required=False, read_only=True)
    oidc_pkce = BooleanField(required=False, read_only=True)
    oidc_fetch_userinfo = BooleanField(required=False, read_only=True)
    oidc_rp_initiated_logout = BooleanField(required=False, read_only=True)
    oidc_admin_group_set = BooleanField(required=False, read_only=True)
    oidc_scope_custom = BooleanField(required=False, read_only=True)
    oidc_username_claim_custom = BooleanField(required=False, read_only=True)
    oidc_groups_claim_custom = BooleanField(required=False, read_only=True)
    oidc_token_auth_method = CharField(required=False, read_only=True, allow_blank=True)
    user_age_ceiling_count = IntegerField(required=False, read_only=True)
    auth_group_exclude_count = IntegerField(required=False, read_only=True)


class StatsEmailSerializer(Serializer):
    """Outbound Email. The host, account and addresses are never reported."""

    smtp_configured = BooleanField(required=False, read_only=True)
    smtp_use_tls = BooleanField(required=False, read_only=True)
    smtp_use_ssl = BooleanField(required=False, read_only=True)


class StatsThrottleSerializer(Serializer):
    """Rate Limits. Zero means the scope is unthrottled."""

    throttle_anon = IntegerField(required=False, read_only=True)
    throttle_user = IntegerField(required=False, read_only=True)
    throttle_opds = IntegerField(required=False, read_only=True)
    throttle_opensearch = IntegerField(required=False, read_only=True)
    throttle_reset_password = IntegerField(required=False, read_only=True)


class StatsDeploymentSerializer(Serializer):
    """Deployment Shape. No paths, prefixes or hostnames are reported."""

    remote_user_auth = BooleanField(required=False, read_only=True)
    failed_login_log = BooleanField(required=False, read_only=True)
    failed_login_log_trust_forwarded_for = BooleanField(required=False, read_only=True)
    url_path_prefix_set = BooleanField(required=False, read_only=True)


class StatsSerializer(Serializer):
    """Admin Stats Tab."""

    platform = StatsPlatformSerializer(required=False)
    config = StatsConfigSerializer(required=False)
    sessions = StatsSessionsSerializer(required=False)
    collections = StatsCollectionSerializer(required=False)
    file_types = CountDictField(required=False)
    metadata = StatsComicMetadataSerializer(required=False)
    usage = StatsUsageSerializer(required=False)
    identifiers = CountDictField(required=False)
    admin_flags = StatsAdminFlagsSerializer(required=False)
    tagging = StatsTaggingSerializer(required=False)
    auth = StatsAuthSerializer(required=False)
    email = StatsEmailSerializer(required=False)
    throttle = StatsThrottleSerializer(required=False)
    deployment = StatsDeploymentSerializer(required=False)


class AdminStatsRequestSerializer(Serializer):
    """Admin Stats Tab Request."""

    platform = SerializerChoicesField(
        serializer=StatsPlatformSerializer, required=False
    )
    config = SerializerChoicesField(serializer=StatsConfigSerializer, required=False)
    sessions = SerializerChoicesField(
        serializer=StatsSessionsSerializer, required=False
    )
    collections = SerializerChoicesField(
        serializer=StatsCollectionSerializer, required=False
    )
    file_types = StringListMultipleChoiceField(choices=FILE_TYPES_CHOICES)
    metadata = SerializerChoicesField(
        serializer=StatsComicMetadataSerializer, required=False
    )
    identifiers = StringListMultipleChoiceField(choices=IDENTIFIER_SOURCE_CHOICES)
    usage = SerializerChoicesField(serializer=StatsUsageSerializer, required=False)
    admin_flags = SerializerChoicesField(
        serializer=StatsAdminFlagsSerializer, required=False
    )
    tagging = SerializerChoicesField(serializer=StatsTaggingSerializer, required=False)
    auth = SerializerChoicesField(serializer=StatsAuthSerializer, required=False)
    email = SerializerChoicesField(serializer=StatsEmailSerializer, required=False)
    throttle = SerializerChoicesField(
        serializer=StatsThrottleSerializer, required=False
    )
    deployment = SerializerChoicesField(
        serializer=StatsDeploymentSerializer, required=False
    )


class APIKeySerializer(Serializer):
    """API Key — wraps the ``AK`` :class:`AdminFlag` row's ``value`` column."""

    api_key = CharField(source="value", read_only=True)
