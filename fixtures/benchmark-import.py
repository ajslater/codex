#!/usr/bin/env python3
"""
Benchmark the librarian importer against a synthetic library.

Generates a deterministic mock-comic library (reusing mock_comics),
boots codex against a scratch config dir, and times import scenarios:

- fresh:    import the whole library into an empty database
- noop:     re-import with unchanged files (mtime pre-filter path)
- reimport: forced metadata re-import (prune-heavy update path)

The library is generated once and reused across runs (same --seed =>
identical files), so before/after timings of importer code changes are
comparable. Running the fresh scenario wipes the scratch config dir
(database) first; noop/reimport runs reuse the database populated by a
prior fresh run.

Usage:
    uv run python tasks/benchmark-import.py --count 1000
    uv run python tasks/benchmark-import.py --scenarios reimport --json out.json
"""

import argparse
import json
import random
import shutil
import sys
from dataclasses import asdict
from os import environ
from pathlib import Path
from time import perf_counter
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DIR = Path("/tmp/codex-benchmark-import")  # noqa: S108
_DEFAULT_COUNT = 1000
_DEFAULT_SEED = 42
_SCENARIOS = ("fresh", "noop", "reimport")
_GENERATE_LOG_BATCH = 500


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--count", type=int, default=_DEFAULT_COUNT, help="number of mock comics"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=_DEFAULT_DIR,
        help="scratch root for the comics/ and config/ dirs",
    )
    parser.add_argument(
        "--seed", type=int, default=_DEFAULT_SEED, help="mock library RNG seed"
    )
    parser.add_argument(
        "--scenarios",
        default=",".join(_SCENARIOS),
        help=f"comma separated subset of {_SCENARIOS}",
    )
    parser.add_argument(
        "--regen", action="store_true", help="force regenerating the mock library"
    )
    parser.add_argument(
        "--json", type=Path, default=None, help="also write results to this JSON file"
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="cProfile each scenario; print top functions and dump .prof files",
    )
    args = parser.parse_args()
    args.scenarios = tuple(
        name for name in _SCENARIOS if name in args.scenarios.split(",")
    )
    if not args.scenarios:
        parser.error(f"--scenarios must name at least one of {_SCENARIOS}")
    return args


def _generate_library(comics_dir: Path, count: int, seed: int, *, regen: bool) -> None:
    """Create the mock comic library unless it already matches."""
    sys.path.insert(0, str(_REPO_ROOT))
    from fixutres.mock_comics.mock_comics import create_file

    existing = len(tuple(comics_dir.rglob("*.cbz"))) if comics_dir.exists() else 0
    if existing == count and not regen:
        print(f"Reusing existing mock library: {existing} comics in {comics_dir}")
        return
    if comics_dir.exists():
        shutil.rmtree(comics_dir)
    comics_dir.mkdir(parents=True)
    # mock_comics uses the global random module; seeding it here makes
    # the generated library deterministic for a given (--seed, --count).
    random.seed(seed)
    start = perf_counter()
    for index in range(count):
        create_file(comics_dir, index)
        if (index + 1) % _GENERATE_LOG_BATCH == 0:
            print(f"Generated {index + 1}/{count} mock comics...")
    elapsed = perf_counter() - start
    print(f"Generated {count} mock comics in {elapsed:.1f}s")


def _boot(config_dir: Path) -> None:
    """Point codex at the scratch config dir and initialize the database."""
    config_dir.mkdir(parents=True, exist_ok=True)
    environ["CODEX_CONFIG_DIR"] = str(config_dir)
    environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings")

    import django

    django.setup()

    from codex.startup import codex_init

    if not codex_init():
        msg = "codex_init() failed"
        raise RuntimeError(msg)


def _build_task(scenario: str, library_id: int, paths: frozenset[str]):
    """Build the ImportTask for a scenario."""
    from codex.librarian.scribe.importer.tasks import ImportTask

    if scenario == "fresh":
        return ImportTask(library_id=library_id, files_created=paths)
    if scenario == "noop":
        return ImportTask(library_id=library_id, files_modified=paths)
    # Match the admin Force Reimport task (scribe/force_updater.py):
    # without check_metadata_mtime=False the comicbox workers skip tag
    # re-extraction when the embedded mtime is unchanged and no prune
    # work happens at all.
    return ImportTask(
        library_id=library_id,
        files_modified=paths,
        force_import_metadata=True,
        check_metadata_mtime=False,
    )


def _run_scenario(
    scenario: str, library_id: int, paths: frozenset[str], *, profile: bool
) -> dict[str, Any]:
    """Run one import scenario and collect timings."""
    from threading import Event, Lock

    from loguru import logger

    from codex.librarian.mp_queue import LIBRARIAN_QUEUE
    from codex.librarian.scribe.importer.importer import ComicImporter

    task = _build_task(scenario, library_id, paths)
    importer = ComicImporter(task, logger, LIBRARIAN_QUEUE, Lock(), Event())
    profiler = None
    if profile:
        import cProfile

        profiler = cProfile.Profile()
        profiler.enable()
    start = perf_counter()
    importer.apply()
    elapsed = perf_counter() - start
    if profiler:
        profiler.disable()
        _report_profile(scenario, profiler)
    return {
        "scenario": scenario,
        "elapsed": elapsed,
        "phase_times": dict(importer.phase_times),
        "counts": asdict(importer.counts),
    }


def _report_profile(scenario: str, profiler) -> None:
    """Dump the profile and print the hottest functions."""
    import pstats

    prof_path = Path(f"test-results/benchmark-import-{scenario}.prof")
    prof_path.parent.mkdir(exist_ok=True)
    profiler.dump_stats(prof_path)
    print(f"\n--- profile: {scenario} (full dump: {prof_path}) ---")
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative").print_stats("codex/", 25)


def _report(result: dict[str, Any], count: int) -> None:
    """Print a phase time table for one scenario result."""
    elapsed = result["elapsed"]
    rate = count / elapsed if elapsed else 0.0
    print(
        f"\n=== {result['scenario']}: {count} comics in {elapsed:.2f}s ({rate:.1f}/s) ==="
    )
    phase_times = result["phase_times"]
    # Dotted "phase.step" sub-steps already count inside their parent
    # phase, so only top-level phases sum to the total.
    total = sum(secs for name, secs in phase_times.items() if "." not in name)
    if not total:
        print("no phases ran")
        return
    print(f"{'phase':<40}{'seconds':>10}{'share':>8}")
    for name, secs in sorted(phase_times.items(), key=lambda kv: kv[1], reverse=True):
        print(f"{name:<40}{secs:>10.2f}{secs / total:>8.1%}")
    counts = {key: value for key, value in result["counts"].items() if value}
    print(f"counts: {counts or 'no changes'}")


def main() -> None:
    """Generate the library, boot codex, run and report scenarios."""
    args = _parse_args()
    comics_dir = args.dir / "comics"
    config_dir = args.dir / "config"

    _generate_library(comics_dir, args.count, args.seed, regen=args.regen)
    if "fresh" in args.scenarios and config_dir.exists():
        print(f"Wiping scratch config dir for fresh import: {config_dir}")
        shutil.rmtree(config_dir)
    _boot(config_dir)

    from codex.librarian.mp_queue import LIBRARIAN_QUEUE
    from codex.models import Library

    library, _ = Library.objects.get_or_create(path=str(comics_dir))
    paths = frozenset(str(path) for path in comics_dir.rglob("*.cbz"))

    results = [
        _run_scenario(scenario, library.pk, paths, profile=args.profile)
        for scenario in args.scenarios
    ]
    for result in results:
        _report(result, len(paths))

    if args.json:
        args.json.write_text(json.dumps(results, indent=2))
        print(f"\nWrote results to {args.json}")

    # No librarian daemon is consuming the queue; don't let its feeder
    # thread block interpreter exit.
    LIBRARIAN_QUEUE.cancel_join_thread()


if __name__ == "__main__":
    main()
