"""
The validation limits shared by the server and the admin client.

Every number in ``codex.choices.limits`` is enforced somewhere on the
server; the client reads the generated JSON rather than re-typing them.
That is what makes a repeat of #867 -- a minimum-length rule comparing
against a constant nobody had wired up -- impossible rather than merely
unlikely, so these tests pin both halves of the contract:

* the dump round-trips to the camelCase shape the client reads, and
* each limit still matches the server rule it claims to describe,
  including the three widths Django owns rather than Codex.
"""

import json

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase

from codex.choices.choices_to_json import (
    _MAP_DUMPS,
    _make_json_serializable,
)
from codex.choices.limits import (
    EMAIL_MAX_LENGTH,
    GROUP_NAME_MAX_LENGTH,
    LIMITS,
    MAX_FIELD_LEN,
    MAX_NAME_LEN,
    MAX_PATH_LEN,
    OIDC_URL_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
)
from codex.models.admin import OIDCSettings
from codex.models.base import (
    MAX_FIELD_LEN as BASE_MAX_FIELD_LEN,
)
from codex.models.base import (
    MAX_NAME_LEN as BASE_MAX_NAME_LEN,
)
from codex.models.base import (
    MAX_PATH_LEN as BASE_MAX_PATH_LEN,
)

_MIN_LENGTH_VALIDATOR = "django.contrib.auth.password_validation.MinimumLengthValidator"


def _password_min_length_option() -> int:
    """Return the only server-side password-length enforcement there is."""
    for validator in settings.AUTH_PASSWORD_VALIDATORS:
        if validator["NAME"] == _MIN_LENGTH_VALIDATOR:
            return validator["OPTIONS"]["min_length"]
    msg = "No MinimumLengthValidator configured"
    raise AssertionError(msg)


class LimitsDumpTestCase(SimpleTestCase):
    """The transport itself."""

    def test_limits_is_registered_for_the_dump(self) -> None:
        """Otherwise the client's import resolves to nothing."""
        assert _MAP_DUMPS["limits.json"] is LIMITS

    def test_the_dump_round_trips_to_camel_case(self) -> None:
        """The shape the client actually reads."""
        dumped = _make_json_serializable(LIMITS)
        # Survives a real JSON round trip, which is what ships.
        dumped = json.loads(json.dumps(dumped))

        assert dumped["passwordMinLength"] == PASSWORD_MIN_LENGTH
        assert dumped["maxNameLen"] == MAX_NAME_LEN

    def test_range_pairs_dump_as_two_element_lists(self) -> None:
        """
        ``$intRange`` takes ``[min, max]`` as its first positional arg.

        A tuple that dumped as anything else would make every bounded
        rule silently wrong rather than loudly broken.
        """
        dumped = json.loads(json.dumps(_make_json_serializable(LIMITS)))
        for key in ("smtpPort", "smtpTimeoutSeconds", "customCoverMaxUploadMb"):
            value = dumped[key]
            assert isinstance(value, list), key
            assert len(value) == 2, key  # noqa: PLR2004
            assert value[0] < value[1], key

    def test_no_django_import_at_module_scope(self) -> None:
        """
        ``codex.settings`` imports this module, so it must stay inert.

        A Django or comicbox import here would make it unimportable
        before the app registry is ready.
        """
        source = __import__("codex.choices.limits", fromlist=["limits"]).__file__
        assert source
        text = __import__("pathlib").Path(source).read_text()
        for banned in ("import django", "from django", "import comicbox"):
            assert banned not in text, banned


class LimitsMatchTheServerTestCase(SimpleTestCase):
    """Each limit still describes the rule it claims to."""

    def test_password_minimum_is_the_one_django_enforces(self) -> None:
        """The client's number and the server's are the same number."""
        assert _password_min_length_option() == PASSWORD_MIN_LENGTH

    def test_the_model_widths_are_re_exported_not_redefined(self) -> None:
        """``codex.models.base`` imports these rather than retyping them."""
        assert BASE_MAX_PATH_LEN is MAX_PATH_LEN
        assert BASE_MAX_NAME_LEN is MAX_NAME_LEN
        assert BASE_MAX_FIELD_LEN is MAX_FIELD_LEN

    def test_the_oidc_url_width_matches_its_column(self) -> None:
        """Replacing the literal must not have changed the schema."""
        field = OIDCSettings._meta.get_field("server_url")
        assert field.max_length == OIDC_URL_MAX_LENGTH

    def test_django_owned_widths(self) -> None:
        """
        Tripwires, not definitions.

        Codex does not own these columns, so a Django upgrade that
        changes one should fail here rather than silently letting the
        client accept a value the server will reject.
        """
        assert User._meta.get_field("username").max_length == USERNAME_MAX_LENGTH
        assert User._meta.get_field("email").max_length == EMAIL_MAX_LENGTH
        assert Group._meta.get_field("name").max_length == GROUP_NAME_MAX_LENGTH
