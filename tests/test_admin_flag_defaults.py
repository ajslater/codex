"""
Which admin flags a fresh install seeds on, and which seed off.

Auto Update is the conditional one. Installing a new codex over the
running one is what a pip, pipx or uv install wants, so it seeds on
there. A container is an immutable deployment — the next restart brings
the image's version back — so docker seeds it off and updates by image
pull instead.
"""

from typing import override
from unittest.mock import patch

from django.test import TestCase

from codex.choices.admin import AdminFlagChoices
from codex.models.admin import AdminFlag
from codex.startup import init_admin_flags

_MODULE = "codex.models.admin"


class AdminFlagDefaultsTests(TestCase):
    """init_admin_flags seeding."""

    @staticmethod
    def _seed(*, docker: bool) -> None:
        with patch(f"{_MODULE}.is_docker", return_value=docker):
            init_admin_flags()

    @staticmethod
    def _on(key: AdminFlagChoices) -> bool:
        return AdminFlag.objects.values_list("on", flat=True).get(key=key.value)

    @override
    def setUp(self) -> None:
        AdminFlag.objects.all().delete()

    def test_auto_update_seeds_on_outside_docker(self) -> None:
        """A pip, pipx or uv install keeps itself up to date by default."""
        self._seed(docker=False)

        assert self._on(AdminFlagChoices.AUTO_UPDATE)

    def test_auto_update_seeds_off_in_docker(self) -> None:
        """An in-place upgrade of a container is thrown away by the restart."""
        self._seed(docker=True)

        assert not self._on(AdminFlagChoices.AUTO_UPDATE)

    def test_register_verification_seeds_off_everywhere(self) -> None:
        """
        The unconditional false default is unaffected.

        Verification needs an SMTP host configured before it can do
        anything but lock new accounts out, so it waits to be turned on.
        """
        for docker in (False, True):
            with self.subTest(docker=docker):
                AdminFlag.objects.all().delete()
                self._seed(docker=docker)

                assert not self._on(AdminFlagChoices.REGISTER_VERIFICATION)

    def test_every_other_flag_seeds_on(self) -> None:
        """Only the two false defaults seed off."""
        self._seed(docker=False)

        off = set(AdminFlag.objects.filter(on=False).values_list("key", flat=True))
        assert off == {AdminFlagChoices.REGISTER_VERIFICATION.value}

    def test_an_admin_who_turns_it_off_stays_off(self) -> None:
        """
        Seeding is get_or_create, so a boot never revives the flag.

        The seed is a default for a row that doesn't exist yet, not an
        opinion reasserted over the admin's on every restart.
        """
        self._seed(docker=False)
        AdminFlag.objects.filter(key=AdminFlagChoices.AUTO_UPDATE.value).update(
            on=False
        )

        self._seed(docker=False)

        assert not self._on(AdminFlagChoices.AUTO_UPDATE)
