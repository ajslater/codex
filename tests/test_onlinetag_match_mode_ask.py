"""
The match modes codex offers are comicbox's, ask included.

comicbox 5.3.1 accepts ``MatchMode.ASK`` from a session with a prompt
handler, which codex always supplies, so the mode that prompts for every
match is offered end to end: the admin default, the launcher, the start
endpoint and the session comicbox runs.
"""

from unittest.mock import patch

from comicbox.config.online import MatchMode
from django.test import SimpleTestCase

from codex.choices.admin import TAGGING_CHOICES
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.models import ComicboxTaggingDefaults
from codex.serializers.admin.tagging import OnlineTagStartSerializer
from tests.onlinetag_session_fakes import (
    PATCH_TARGET,
    FakePassRunner,
    FakeSession,
    OnlineTagSessionTestCase,
    double,
    make_comic,
)


class MatchModeChoicesTests(SimpleTestCase):
    """Every mode comicbox has, in its order, and nothing comicbox lacks."""

    def test_the_model_choices_are_comicboxs_enum(self) -> None:
        values = [choice.value for choice in ComicboxTaggingDefaults.MatchModeChoices]
        assert values == [mode.value for mode in MatchMode]
        assert "ask" in values

    def test_the_ui_choices_are_comicboxs_enum(self) -> None:
        assert list(TAGGING_CHOICES["matchMode"]) == [mode.value for mode in MatchMode]
        assert TAGGING_CHOICES["matchMode"] == {
            mode.value: mode.value.capitalize() for mode in MatchMode
        }

    def test_the_default_is_still_auto(self) -> None:
        field = ComicboxTaggingDefaults._meta.get_field("default_match_mode")
        assert field.default == "auto"


class StartSerializerModeTests(SimpleTestCase):
    """The start endpoint refuses a mode comicbox would reject in the librarian."""

    @staticmethod
    def _validate(mode: str) -> OnlineTagStartSerializer:
        serializer = OnlineTagStartSerializer(
            data={"collection": "comics", "pks": ["1"], "mode": mode}
        )
        serializer.is_valid()
        return serializer

    def test_ask_is_accepted(self) -> None:
        serializer = self._validate("ask")
        assert not serializer.errors
        assert serializer.validated_data["mode"] == "ask"

    def test_an_unknown_mode_is_rejected(self) -> None:
        assert "mode" in self._validate("reckless").errors


class SessionMatchModeTests(OnlineTagSessionTestCase):
    """The task's mode reaches comicbox as its enum member."""

    def test_ask_reaches_the_session(self) -> None:
        comic = make_comic()
        self.manager._pass_runner = double(FakePassRunner())  # noqa: SLF001
        task = BulkOnlineTagTask(
            comic_pks=frozenset({comic.pk}),
            session_id="scan-ask",
            sources=("metron",),
            mode="ask",
        )

        with patch(PATCH_TARGET, FakeSession):
            self.manager.run_session(task)

        assert FakeSession.last_kwargs["match"] is MatchMode.ASK
        # The resolver comicbox requires for ask: codex's own prompt handler.
        assert FakeSession.last_kwargs["prompt_handler"] is not None
