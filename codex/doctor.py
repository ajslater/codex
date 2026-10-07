"""
comicbox's doctor, run for this install.

comicbox 5.3.0's ``run_checks`` reports whether this host can read each
archive format, whether Pillow has the codecs cover matching needs, whether
the user's comicbox config parses, and whether comicbox's package pins are
satisfied, with a one-line fix for anything that is not. Codex shows the
rows to admins and logs the problems once at startup, so a missing unrar or
a pymupdf built against the wrong libmupdf is explained in one place rather
than discovered as failed imports with no cause.

The Online section is left out. Codex keeps the tagging credentials in its
own database and checks them on the Tagging tab, so the doctor's "no
credentials" rows and its ``--online`` advice would describe the CLI, not
this server.

comicbox caches its tool probes for the life of the process, so a tool
installed while codex runs shows up after a restart.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from comicbox.doctor import Status, run_checks
from comicbox.doctor.online import SECTION as _ONLINE_SECTION

if TYPE_CHECKING:
    from comicbox.doctor import CheckResult, DoctorReport
    from loguru import Logger


def run_doctor() -> DoctorReport:
    """Run comicbox's doctor and keep the rows that describe this server."""
    report = run_checks()
    results = tuple(row for row in report.results if row.section != _ONLINE_SECTION)
    return replace(report, results=results)


def problem_count(report: DoctorReport) -> int:
    """Count the rows that say something comicbox needs is broken."""
    return sum(row.status.is_failure for row in report.results)


def _describe(row: CheckResult) -> str:
    """One log line for a row: what, how bad, why, and the fix if there is one."""
    line = f"comicbox doctor: {row.name} {row.status}: {row.detail}"
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
        log.warning(f"comicbox doctor found {problems} {noun}. See the Admin Jobs tab.")
    else:
        log.debug("comicbox doctor found no problems.")
