"""
Settings counted in registered users, not in settings rows.

The failure these guard against is quiet: every number here is plausible when
it is wrong, because the buckets are small integers either way. So the tests
assert the two structural properties that make them readable at all -- the
live/global families partition, and the chosen families never claim an
untouched user chose anything.
"""

from types import MappingProxyType
from typing import Final

from django.contrib.auth.models import User
from django.test import TestCase

from codex.librarian.telemeter.per_user_stats import (
    BROWSER_FIELDS,
    READER_FIELDS,
    get_per_user_stats,
)
from codex.models.named import StoryArc
from codex.models.settings import (
    ClientChoices,
    SettingsBrowser,
    SettingsBrowserShow,
    SettingsReader,
)

_API: Final = ClientChoices.API
# One reader with a global row, one with only a scoped row.
_TWO_READERS: Final = 2
# A global reader row is one with every scope FK null.
_GLOBAL_SCOPE: Final[MappingProxyType[str, None]] = MappingProxyType(
    {"comic": None, "series": None, "folder": None, "story_arc": None}
)


def _user(name: str) -> User:
    return User.objects.create_user(username=name)


def _browser(user: User, **kwargs) -> SettingsBrowser:
    """
    Create a browser settings row, with the show row it cannot exist without.

    The real code path builds show/filters/last_route together; the collector
    reads none of them, so the minimum that satisfies the FK is enough here.
    """
    show, _ = SettingsBrowserShow.objects.get_or_create(
        publishers=True, imprints=False, series=True, volumes=False
    )
    return SettingsBrowser.objects.create(user=user, show=show, **kwargs)


class PerUserStatsTestCase(TestCase):
    """The per_user section."""

    def test_reader_fields_match_the_model(self) -> None:
        """A field added to SettingsReader must be reported or removed here."""
        assert set(READER_FIELDS) == set(SettingsReader.DIRECT_KEYS)

    def test_no_registered_users_still_reports(self) -> None:
        """
        Zero counts, not an absent section.

        An absent section has to mean "this codex cannot answer"; an install
        with no accounts is answering, and the answer is none.
        """
        stats = get_per_user_stats()
        assert stats["browser_user_count"] == 0
        assert stats["reader_user_count"] == 0
        for field in BROWSER_FIELDS:
            assert stats[f"browser_{field}_users"] == {}

    def test_browser_live_row_partitions(self) -> None:
        """
        Each user votes once, whatever else they have saved.

        The unique constraint is on (user, client, name), so saved settings and
        OPDS rows are extra rows for the same user. Counting them here would
        make a user with three saved views outweigh two people.
        """
        user = _user("one")
        _browser(user, client=_API, name="")
        _browser(user, client=_API, name="saved")
        _browser(user, client=ClientChoices.OPDS, name="")

        stats = get_per_user_stats()
        assert stats["browser_user_count"] == 1
        for field in BROWSER_FIELDS:
            counts = stats[f"browser_{field}_users"]
            assert sum(counts.values()) == 1, field

    def test_browser_reach_sees_saved_and_opds_rows(self) -> None:
        """
        The live row shows current state; reach shows use.

        A user who saved a table view and is currently on covers has used
        table view, and the pruning question needs to see that.
        """
        user = _user("two")
        _browser(user, client=_API, name="", view_mode="cover")
        _browser(user, client=_API, name="tables", view_mode="table")

        stats = get_per_user_stats()
        assert stats["browser_view_mode_users"] == {"cover": 1}
        assert stats["browser_chosen_view_mode_users"] == {"cover": 1, "table": 1}

    def test_reader_global_counts_untouched_as_unset(self) -> None:
        """
        An all-unset global row is the normal case, and it is the signal.

        codex creates the global row from the params path without applying
        READER_DEFAULTS, so most users have one that sets nothing. Reporting
        that as "" is what makes "is the default tolerated" answerable.
        """
        user = _user("three")
        SettingsReader.objects.create(user=user, client=_API, **_GLOBAL_SCOPE)

        stats = get_per_user_stats()
        assert stats["reader_user_count"] == 1
        for field in READER_FIELDS:
            assert stats[f"reader_global_{field}_users"] == {"": 1}, field

    def test_reader_global_partitions_over_every_reader_user(self) -> None:
        """
        A user with only a scoped row still votes, and votes unset.

        They have touched the reader without ever setting a global preference,
        which is what the untouched key means. Leaving them out would make the
        histogram partition over a subset and quietly shrink the denominator
        that every share on the dashboard is taken over.
        """
        globally = _user("four")
        SettingsReader.objects.create(
            user=globally, client=_API, fit_to="H", **_GLOBAL_SCOPE
        )
        scoped_only = _user("five")
        arc = StoryArc.objects.create(name="Arc")
        SettingsReader.objects.create(
            user=scoped_only, client=_API, story_arc=arc, fit_to="S"
        )

        stats = get_per_user_stats()
        assert stats["reader_user_count"] == _TWO_READERS
        assert stats["reader_scoped_user_count"] == 1
        assert stats["reader_global_fit_to_users"] == {"H": 1, "": 1}
        for field in READER_FIELDS:
            counts = stats[f"reader_global_{field}_users"]
            assert sum(counts.values()) == stats["reader_user_count"], field

    def test_reader_chosen_never_carries_unset(self) -> None:
        """
        Choosing is by definition not leaving it alone.

        "" in a chosen bucket would double count every untouched user as
        having picked something, and the pruning read would be worthless.
        """
        user = _user("chooser")
        SettingsReader.objects.create(
            user=user, client=_API, fit_to="S", **_GLOBAL_SCOPE
        )

        stats = get_per_user_stats()
        for field in READER_FIELDS:
            assert "" not in stats[f"reader_chosen_{field}_users"], field
        assert stats["reader_chosen_fit_to_users"] == {"S": 1}

    def test_reader_chosen_counts_a_user_once_per_value(self) -> None:
        """
        One enthusiast with three manga arcs is one person, not three.

        Reach asks how many people reach for a value. Counting rows is what
        the sessions buckets already do, and it is why one install with a big
        session table can speak for the whole fleet.
        """
        user = _user("six")
        SettingsReader.objects.create(
            user=user, client=_API, reading_direction="ltr", **_GLOBAL_SCOPE
        )
        for index in range(3):
            arc = StoryArc.objects.create(name=f"Arc {index}")
            SettingsReader.objects.create(
                user=user, client=_API, story_arc=arc, reading_direction="rtl"
            )

        stats = get_per_user_stats()
        assert stats["reader_chosen_reading_direction_users"] == {"ltr": 1, "rtl": 1}
        assert stats["reader_global_reading_direction_users"] == {"ltr": 1}

    def test_bucket_keys_render_booleans_as_words(self) -> None:
        """
        A nullable boolean and a blank char field must say unset the same way.

        Chronicle stores both families in one char-keyed table, so True/False/
        None have to arrive as "true"/"false"/"".
        """
        user = _user("seven")
        SettingsReader.objects.create(
            user=user, client=_API, two_pages=True, **_GLOBAL_SCOPE
        )

        stats = get_per_user_stats()
        assert stats["reader_global_two_pages_users"] == {"true": 1}
        assert stats["reader_global_cache_book_users"] == {"": 1}
