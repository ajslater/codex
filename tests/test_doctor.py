"""
The doctor as codex runs it.

comicbox's report is comicbox's; what codex adds is dropping the Online
section, appending its own rows, counting the problems, and logging them
once at startup.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from comicbox.doctor import CheckResult, DoctorReport, Status
from comicbox.doctor.online import SECTION as ONLINE_SECTION
from django.test import TestCase

from codex.doctor import log_doctor_problems, run_doctor
from codex.doctor.checks import SECTION as CODEX_SECTION

_HEADER = ("comicbox 5.3.0", "Python 3.14.4", "Linux-6.1")
_CBR_MISSING = CheckResult(
    "Archives",
    "CBR",
    Status.MISSING,
    found="rarfile 4.5",
    detail="no RAR tool found: 'unrar' not on path",
    fix="apt install unrar (Debian: enable non-free)",
)
_PDF_OK = CheckResult(
    "Archives", "PDF", Status.OK, found="comicbox-pdffile 1.0.0", detail="pymupdf"
)
_UNKNOWN_KEY = CheckResult(
    "Config",
    "unknown key",
    Status.WARN,
    found=Path("/config/comicbox.yaml"),
    detail="general.loglevl is ignored",
    fix="did you mean general.loglevel?",
)
_METRON = CheckResult(ONLINE_SECTION, "metron", Status.OFF, detail="no credentials")
_REPORT = DoctorReport(
    header=_HEADER, results=(_CBR_MISSING, _PDF_OK, _UNKNOWN_KEY, _METRON)
)
_DATABASE_OK = CheckResult(CODEX_SECTION, "database", Status.OK, detail="fts5 · wal")


def _patched(report: DoctorReport = _REPORT):
    return patch("codex.doctor.run_checks", return_value=report)


def _codex_rows(*rows: CheckResult):
    """Stand in for every codex check with fixed rows."""
    return patch("codex.doctor.CHECKS", (("codex", lambda: rows),))


class RunDoctorTests(TestCase):
    """What codex keeps of comicbox's report, and what it adds."""

    def test_drops_the_online_section_and_keeps_codex_rows_apart(self) -> None:
        """Codex checks credentials on the Tagging tab, from its own database."""
        with _patched(), _codex_rows(_DATABASE_OK):
            report = run_doctor()
        assert report.header == _HEADER
        assert report.comicbox == (_CBR_MISSING, _PDF_OK, _UNKNOWN_KEY)
        assert report.codex == (_DATABASE_OK,)
        assert report.results == (_CBR_MISSING, _PDF_OK, _UNKNOWN_KEY, _DATABASE_OK)

    def test_problems_are_failures_not_warnings(self) -> None:
        with _patched(), _codex_rows(_DATABASE_OK):
            report = run_doctor()
        assert report.problems == 1

    def test_a_crashing_codex_check_is_one_error_row(self) -> None:
        def explode():
            msg = "boom"
            raise RuntimeError(msg)

        with _patched(), patch("codex.doctor.CHECKS", (("watcher", explode),)):
            report = run_doctor()
        assert report.codex == (
            CheckResult(
                CODEX_SECTION, "watcher", Status.ERROR, detail="RuntimeError: boom"
            ),
        )

    def test_the_real_doctor_runs(self) -> None:
        """Unpatched: comicbox's checks and codex's run here, whatever they find."""
        report = run_doctor()
        assert report.header
        assert {"CBZ", "CBR", "PDF", "Pillow", "cover hash"} <= {
            row.name for row in report.comicbox
        }
        assert {"database", "config dir", "library", "watcher", "credentials"} <= {
            row.name for row in report.codex
        }
        assert not any(row.section == ONLINE_SECTION for row in report.comicbox)


class LogDoctorProblemsTests(TestCase):
    """Failures warn with their fix, warnings inform, and a verdict closes."""

    def test_failures_warn_with_the_fix(self) -> None:
        log = MagicMock()
        with _patched(), _codex_rows(_DATABASE_OK):
            log_doctor_problems(log)
        warnings = [call.args[0] for call in log.warning.call_args_list]
        assert warnings == [
            (
                "doctor: CBR MISSING: no RAR tool found: 'unrar' not on path"
                " Fix: apt install unrar (Debian: enable non-free)"
            ),
            "The doctor found 1 problem. See the Admin Doctor tab.",
        ]

    def test_warnings_inform(self) -> None:
        log = MagicMock()
        with _patched(), _codex_rows(_DATABASE_OK):
            log_doctor_problems(log)
        infos = [call.args[0] for call in log.info.call_args_list]
        assert infos == [
            (
                "doctor: unknown key WARN: general.loglevl is ignored"
                " Fix: did you mean general.loglevel?"
            )
        ]

    def test_a_clean_report_is_quiet(self) -> None:
        log = MagicMock()
        clean = DoctorReport(header=_HEADER, results=(_PDF_OK, _METRON))
        with _patched(clean), _codex_rows(_DATABASE_OK):
            log_doctor_problems(log)
        log.warning.assert_not_called()
        log.info.assert_not_called()
        log.debug.assert_called_once()
