"""
comicbox's doctor as codex runs it.

The report is comicbox's; what codex adds is dropping the Online section,
counting the problems, and logging them once at startup.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from comicbox.doctor import CheckResult, DoctorReport, Status
from comicbox.doctor.online import SECTION as ONLINE_SECTION

from codex.doctor import log_doctor_problems, problem_count, run_doctor

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


def _patched(report: DoctorReport = _REPORT):
    return patch("codex.doctor.run_checks", return_value=report)


class TestRunDoctor:
    """What codex keeps of comicbox's report."""

    def test_drops_the_online_section(self) -> None:
        """Codex checks credentials on the Tagging tab, from its own database."""
        with _patched():
            report = run_doctor()
        assert report.header == _HEADER
        assert report.results == (_CBR_MISSING, _PDF_OK, _UNKNOWN_KEY)

    def test_problems_are_failures_not_warnings(self) -> None:
        with _patched():
            report = run_doctor()
        assert problem_count(report) == 1

    def test_the_real_doctor_runs(self) -> None:
        """Unpatched: comicbox's checks run here, whatever they find."""
        report = run_doctor()
        assert report.header
        names = {row.name for row in report.results}
        assert {"CBZ", "CBR", "PDF", "Pillow", "cover hash"} <= names
        assert not any(row.section == ONLINE_SECTION for row in report.results)


class TestLogDoctorProblems:
    """Failures warn with their fix, warnings inform, and a verdict closes."""

    def test_failures_warn_with_the_fix(self) -> None:
        log = MagicMock()
        with _patched():
            log_doctor_problems(log)
        warnings = [call.args[0] for call in log.warning.call_args_list]
        assert warnings == [
            (
                "comicbox doctor: CBR MISSING: no RAR tool found: 'unrar' not on path"
                " Fix: apt install unrar (Debian: enable non-free)"
            ),
            "comicbox doctor found 1 problem. See the Admin Jobs tab.",
        ]

    def test_warnings_inform(self) -> None:
        log = MagicMock()
        with _patched():
            log_doctor_problems(log)
        infos = [call.args[0] for call in log.info.call_args_list]
        assert infos == [
            (
                "comicbox doctor: unknown key WARN: general.loglevl is ignored"
                " Fix: did you mean general.loglevel?"
            )
        ]

    def test_a_clean_report_is_quiet(self) -> None:
        log = MagicMock()
        with _patched(DoctorReport(header=_HEADER, results=(_PDF_OK, _METRON))):
            log_doctor_problems(log)
        log.warning.assert_not_called()
        log.info.assert_not_called()
        log.debug.assert_called_once()
