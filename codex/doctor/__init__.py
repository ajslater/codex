"""
The doctor: comicbox's health checks plus codex's own, for this install.

comicbox 5.3.0's ``run_checks`` reports whether this host can read each
archive format, whether Pillow has the codecs cover matching needs, whether
the user's comicbox config parses, and whether comicbox's package pins are
satisfied, with a one-line fix for anything that is not. Codex adds the
checks for what it needs on top (``codex.doctor.checks``), shows the rows
to admins, and logs the problems once at startup, so a missing unrar or a
full disk is explained in one place rather than discovered as failed
imports with no cause.

comicbox's Online section is left out. Codex keeps the tagging credentials
in its own database and checks them on the Tagging tab, so the doctor's "no
credentials" rows and its ``--online`` advice would describe the CLI, not
this server.

comicbox caches its tool probes for the life of the process, so a tool
installed while codex runs shows up after a restart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from comicbox.doctor import CheckResult, DoctorReport, Status, run_checks
from comicbox.doctor.online import SECTION as _ONLINE_SECTION

from codex.doctor.checks import CHECKS, SECTION

if TYPE_CHECKING:
    from loguru import Logger

    from codex.doctor.checks import Check


def _run_check(name: str, check: Check) -> list[CheckResult]:
    """Run one codex check; a crash becomes one ERROR row and hides nothing else."""
    rows: list[CheckResult] = []
    try:
        rows.extend(check())
    except Exception as exc:  # reported as the row
        rows.append(
            CheckResult(
                SECTION, name, Status.ERROR, detail=f"{type(exc).__name__}: {exc}"
            )
        )
    return rows


def run_doctor() -> DoctorReport:
    """Run comicbox's doctor and codex's checks; keep the rows that describe this server."""
    report = run_checks()
    comicbox_rows = [row for row in report.results if row.section != _ONLINE_SECTION]
    codex_rows = [row for name, check in CHECKS for row in _run_check(name, check)]
    return DoctorReport(header=report.header, results=(*comicbox_rows, *codex_rows))


def problem_count(report: DoctorReport) -> int:
    """Count the rows that say something codex needs is broken."""
    return sum(row.status.is_failure for row in report.results)


def _describe(row: CheckResult) -> str:
    """One log line for a row: what, how bad, why, and the fix if there is one."""
    line = f"doctor: {row.name} {row.status}: {row.detail}"
    if row.fix:
        line += f" Fix: {row.fix}"
    return line


def log_doctor_problems(log: Logger) -> None:
    """
    Log what the doctor found, once, after logging is configured.

    Failures warn and warnings inform. The scanner used to warn about an
    unreadable archive format at import time, before any log sink existed,
    so the message only ever reached stderr.
    """
    report = run_doctor()
    for row in report.results:
        if row.status.is_failure:
            log.warning(_describe(row))
        elif row.status is Status.WARN:
            log.info(_describe(row))
    if problems := problem_count(report):
        noun = "problem" if problems == 1 else "problems"
        log.warning(f"The doctor found {problems} {noun}. See the Admin Doctor tab.")
    else:
        log.debug("The doctor found no problems.")
