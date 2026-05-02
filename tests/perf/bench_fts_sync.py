r"""
Benchmark FTS5 sync strategies for SearchIndexSyncManyToManyImporter.

Compares three strategies for rewriting one or more columns of N
ComicFTS rows after an m2m relation changes:

  A) Django bulk_update — current production path.
  B) filter().delete() + bulk_create — wrapped in transaction.atomic.
  C) Raw SQL UPDATE … WHERE comic_id IN (…) — bypasses ORM CASE-WHEN.

The script seeds a fresh sqlite3 file with synthetic Comic + ComicFTS
rows, snapshots it, then runs each strategy from the same starting
state across a sweep of sizes and field counts. Median wall time per
combo is reported.

Usage::

    DEBUG=0 uv run --no-sync python -m tests.perf.bench_fts_sync \
        --out tasks/fts-sync-bench.json

    # Or to pin a specific sweep:
    DEBUG=0 uv run --no-sync python -m tests.perf.bench_fts_sync \
        --table-sizes 10000 50000 \
        --affected-counts 100 1000 10000 \
        --field-counts 1 3 10 \
        --runs 5 --out tasks/fts-sync-bench.json

The script uses an isolated sqlite3 file in a tmp directory; it does
not touch ``$CODEX_CONFIG_DIR/codex.sqlite3``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# Pin everything before django.setup runs.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="codex-fts-bench-"))
os.environ["CODEX_CONFIG_DIR"] = str(_TMP_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings")
os.environ["DEBUG"] = "0"
os.environ.setdefault("LOGLEVEL", "WARNING")

# `codex/__init__.py` calls django.setup(); run it as a statement so
# ruff's import sorter can't reorder it below the django imports that
# require apps.populate() to have completed.
importlib.import_module("codex")

from django.core.management import call_command  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from django.db.models.functions.datetime import Now  # noqa: E402

from codex.librarian.scribe.search.const import COMICFTS_UPDATE_FIELDS  # noqa: E402
from codex.models.comic import ComicFTS  # noqa: E402

# codex_comicfts is an FTS5 virtual table (unmanaged); the Comic FK
# isn't enforced at the storage layer, so the bench skips Comic
# entirely and inserts raw rows. This avoids paying for Comic's
# parent FK chain (Publisher/Imprint/Series/Volume) and isolates the
# measurement to the FTS5 sync path.
_COMICFTS_COLUMNS = (
    "comic_id",
    "created_at",
    "updated_at",
    "collection_title",
    "name",
    "review",
    "summary",
    "publisher",
    "imprint",
    "series",
    "age_rating_tagged",
    "age_rating_metron",
    "country",
    "language",
    "original_format",
    "scan_info",
    "tagger",
    "characters",
    "credits",
    "genres",
    "locations",
    "series_groups",
    "sources",
    "stories",
    "story_arcs",
    "tags",
    "teams",
    "universes",
)

# Realistic-ish corpora so FTS5 segments aren't degenerate.
_SERIES_CORPUS = (
    "Captain Science",
    "Astro Adventures",
    "Quantum Reach",
    "Ironblood",
    "Photon Patrol",
    "Strange Vectors",
    "Vault of Mysteries",
    "Cosmic Tide",
    "The Last Convoy",
    "Nightfall Brigade",
)
_CHAR_CORPUS = (
    "Captain Science",
    "Boy Empirical",
    "Doctor Onishi",
    "Kei",
    "Kiyoko",
    "Masaru",
    "Nezu",
    "Ryu",
    "Tetsuo",
    "Akira",
    "Colonel Shikishima",
    "The Architect",
    "Lt. Vega",
    "Sergeant Holt",
)
_TAG_CORPUS = (
    "post-apocalyptic",
    "psionic",
    "espionage",
    "future-noir",
    "hard-sf",
    "biopunk",
    "cyberpunk",
    "mecha",
    "first-contact",
    "time-travel",
    "alternate-history",
    "anti-hero",
)
_CRED_CORPUS = (
    "Joe Orlando",
    "Wally Wood",
    "Jack Kirby",
    "Stan Lee",
    "Alan Moore",
    "Frank Miller",
    "Brian K. Vaughan",
    "Fiona Staples",
    "Saladin Ahmed",
    "Marjorie Liu",
)


def _join_sample(corpus: tuple[str, ...], k: int, rng: random.Random) -> str:
    return ",".join(rng.sample(corpus, k))


def _seed(n_comics: int, rng: random.Random) -> None:
    """Insert n_comics ComicFTS rows directly into the FTS5 virtual table."""
    print(f"  seeding {n_comics:,} ComicFTS rows…", flush=True)
    t0 = time.perf_counter()

    placeholders = ",".join("?" * len(_COMICFTS_COLUMNS))
    sql = (
        f"INSERT INTO codex_comicfts ({','.join(_COMICFTS_COLUMNS)}) "  # noqa: S608
        f"VALUES ({placeholders})"
    )

    batch_size = 2000
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        for start in range(0, n_comics, batch_size):
            end = min(start + batch_size, n_comics)
            rows = [
                (
                    pk,
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:00:00",
                    rng.choice(_SERIES_CORPUS),
                    f"Issue {pk % 200}",
                    "",
                    "An adventure unfolds.",
                    "Youthful Adventure Stories",
                    "TestImprint",
                    rng.choice(_SERIES_CORPUS),
                    "Everyone",
                    "Everyone",
                    "us,United States",
                    "en,English",
                    "Trade Paperback",
                    "Photocopied",
                    "bench",
                    _join_sample(_CHAR_CORPUS, 5, rng),
                    _join_sample(_CRED_CORPUS, 3, rng),
                    "Science Fiction,Adventure",
                    "The Moon",
                    "science comics",
                    "comicvine",
                    "The Beginning",
                    "Genesis",
                    _join_sample(_TAG_CORPUS, 4, rng),
                    "Team Scientific Method",
                    "Young Adult Silly Universe",
                )
                for pk in range(start + 1, end + 1)
            ]
            cursor.executemany(sql, rows)
        # Optimize so segment state is consistent before strategies run.
        cursor.execute(
            "INSERT INTO codex_comicfts (codex_comicfts) VALUES('optimize')"
        )

    elapsed = time.perf_counter() - t0
    print(f"  seeded in {elapsed:.1f}s", flush=True)


def _make_payload(
    pks: list[int],
    fields: tuple[str, ...],
    rng: random.Random,
) -> dict[int, dict[str, str]]:
    """Build {pk: {field: new_value}} for the chosen affected pks."""
    payload: dict[int, dict[str, str]] = {}
    for pk in pks:
        row: dict[str, str] = {}
        for f in fields:
            # New value differs from seeded one so FTS5 actually rewrites.
            if f == "tags":
                row[f] = _join_sample(_TAG_CORPUS, 5, rng)
            elif f == "characters":
                row[f] = _join_sample(_CHAR_CORPUS, 6, rng)
            elif f == "credits":
                row[f] = _join_sample(_CRED_CORPUS, 4, rng)
            else:
                row[f] = f"bench-{rng.randrange(1, 9999)}"
        payload[pk] = row
    return payload


# ---------- Strategies ----------------------------------------------------


def _strategy_bulk_update(
    payload: dict[int, dict[str, str]], fields: tuple[str, ...]
) -> None:
    """Strategy A — current production path."""
    pks = list(payload.keys())
    objs = list(ComicFTS.objects.filter(comic_id__in=pks).only(*fields))
    for o in objs:
        for field, value in payload[o.comic_id].items():  # pyright: ignore[reportAttributeAccessIssue]
            setattr(o, field, value)
        o.updated_at = Now()
    # SQLite's variable limit caps how many rows Django can pack into
    # a single CASE-WHEN UPDATE; bulk_update will issue multiple
    # statements with batch_size. Use 500 so (n_fields + 1) * 500
    # stays well under the 32k limit even with the big field count.
    ComicFTS.objects.bulk_update(objs, (*fields, "updated_at"), batch_size=500)


def _strategy_delete_create(
    payload: dict[int, dict[str, str]], fields: tuple[str, ...]
) -> None:
    """Strategy B — fetch full rows, delete, bulk_create with new values."""
    pks = list(payload.keys())
    # Fetch all columns so we can rebuild the row.
    existing = {
        o.comic_id: o  # pyright: ignore[reportAttributeAccessIssue]
        for o in ComicFTS.objects.filter(comic_id__in=pks)
    }
    new_objs: list[ComicFTS] = []
    for pk, row in payload.items():
        old = existing.get(pk)
        if old is None:
            continue
        # Apply edits.
        for field, value in row.items():
            setattr(old, field, value)
        old.updated_at = Now()
        new_objs.append(old)
    with transaction.atomic():
        # Chunk delete and create to stay under SQLite's variable limit.
        for start in range(0, len(pks), 500):
            chunk = pks[start : start + 500]
            ComicFTS.objects.filter(comic_id__in=chunk).delete()
        ComicFTS.objects.bulk_create(new_objs, batch_size=500)


def _strategy_raw_update(
    payload: dict[int, dict[str, str]], fields: tuple[str, ...]
) -> None:
    """
    Strategy C — raw UPDATE per (field, value) batch.

    Uses one ``UPDATE … SET col = ? WHERE comic_id IN (…)`` per
    distinct (field, value) tuple. Since synthetic data has unique
    values per pk this collapses to one UPDATE per row, which is the
    pessimistic case for raw SQL but a realistic worst-case (every
    affected comic's tag list is unique).
    """
    pks = list(payload.keys())
    # Group by (field, value) so identical edits collapse to one UPDATE.
    by_field_value: dict[tuple[str, str], list[int]] = {}
    for pk, row in payload.items():
        for field, value in row.items():
            by_field_value.setdefault((field, value), []).append(pk)
    with connection.cursor() as cursor, transaction.atomic():
        for (field, value), pk_group in by_field_value.items():
            # Chunk the IN clause to stay under SQLite's variable limit.
            for start in range(0, len(pk_group), 900):
                chunk = pk_group[start : start + 900]
                placeholders = ",".join("?" * len(chunk))
                cursor.execute(
                    f"UPDATE codex_comicfts "  # noqa: S608
                    f"SET {field} = ?, updated_at = CURRENT_TIMESTAMP "
                    f"WHERE comic_id IN ({placeholders})",
                    [value, *chunk],
                )
        # Avoid unused-arg lint when fields is just informational.
        _ = pks


_STRATEGIES = {
    "A_bulk_update": _strategy_bulk_update,
    "B_delete_create": _strategy_delete_create,
    "C_raw_update": _strategy_raw_update,
}


# ---------- Driver --------------------------------------------------------


def _migrate(db_path: Path) -> None:
    """Apply migrations against the bench DB."""
    print(f"  migrating {db_path}…", flush=True)
    t0 = time.perf_counter()
    call_command("migrate", "--noinput", "-v", "0")
    elapsed = time.perf_counter() - t0
    print(f"  migrated in {elapsed:.1f}s", flush=True)


def _snapshot(db_path: Path, snap_path: Path) -> None:
    # WAL flush before copy so the snapshot is self-contained.
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.close()
    shutil.copy2(db_path, snap_path)


def _restore(db_path: Path, snap_path: Path) -> None:
    connection.close()
    shutil.copy2(snap_path, db_path)
    # Re-open implicitly on next query.
    connection.ensure_connection()


def _fts_optimize() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO codex_comicfts (codex_comicfts) VALUES('optimize')"
        )


def _run_combo(
    *,
    db_path: Path,
    snap_path: Path,
    table_size: int,
    n_affected: int,
    fields: tuple[str, ...],
    runs: int,
    rng: random.Random,
) -> dict[str, list[float]]:
    """Run all strategies on the same starting state ``runs`` times."""
    # Comic pks are 1..table_size by construction. Pick a random
    # subset of size n_affected so the workload exercises non-
    # contiguous rowids in the FTS5 segments.
    pks_pool = list(range(1, table_size + 1))
    rng.shuffle(pks_pool)
    chosen = pks_pool[:n_affected]
    payload = _make_payload(chosen, fields, rng)

    durations: dict[str, list[float]] = {name: [] for name in _STRATEGIES}
    for run in range(runs):
        for name, fn in _STRATEGIES.items():
            _restore(db_path, snap_path)
            _fts_optimize()
            t0 = time.perf_counter()
            fn(payload, fields)
            durations[name].append(time.perf_counter() - t0)
        print(
            f"    run {run + 1}/{runs}: "
            + " ".join(
                f"{n}={durations[n][-1] * 1000:.0f}ms" for n in _STRATEGIES
            ),
            flush=True,
        )
    return durations


def _setup_one_size(table_size: int, db_path: Path, snap_path: Path) -> None:
    """Migrate + seed a fresh DB at ``table_size`` and snapshot it."""
    # Close any open connection so unlink/migrate sees the file fresh.
    connection.close()
    for path in (db_path, snap_path):
        if path.exists():
            path.unlink()
        # Also remove WAL/SHM siblings.
        for suffix in ("-wal", "-shm", "-journal"):
            sib = path.with_name(path.name + suffix)
            if sib.exists():
                sib.unlink()
    _migrate(db_path)
    rng = random.Random(0xC0DE)
    _seed(table_size, rng)
    _snapshot(db_path, snap_path)


def _setup_from_snapshot(
    source: Path, db_path: Path, snap_path: Path
) -> int:
    """Use an existing codex DB as the bench snapshot. Returns ComicFTS row count."""
    connection.close()
    for path in (db_path, snap_path):
        if path.exists():
            path.unlink()
        for suffix in ("-wal", "-shm", "-journal"):
            sib = path.with_name(path.name + suffix)
            if sib.exists():
                sib.unlink()
    shutil.copy2(source, db_path)
    shutil.copy2(source, snap_path)
    connection.ensure_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM codex_comicfts")
        return cursor.fetchone()[0]


def _real_pks(rng: random.Random, n_affected: int) -> list[int]:
    """Pick n_affected random comic_ids from the existing ComicFTS table."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT comic_id FROM codex_comicfts")
        pool = [row[0] for row in cursor.fetchall()]
    rng.shuffle(pool)
    return pool[:n_affected]


def _run_combo_real(
    *,
    db_path: Path,
    snap_path: Path,
    chosen_pks: list[int],
    fields: tuple[str, ...],
    runs: int,
    rng: random.Random,
) -> dict[str, list[float]]:
    """Run all strategies on the same starting state ``runs`` times — real-DB variant."""
    payload = _make_payload(chosen_pks, fields, rng)
    durations: dict[str, list[float]] = {name: [] for name in _STRATEGIES}
    for run in range(runs):
        for name, fn in _STRATEGIES.items():
            _restore(db_path, snap_path)
            _fts_optimize()
            t0 = time.perf_counter()
            fn(payload, fields)
            durations[name].append(time.perf_counter() - t0)
        print(
            f"    run {run + 1}/{runs}: "
            + " ".join(
                f"{n}={durations[n][-1] * 1000:.0f}ms" for n in _STRATEGIES
            ),
            flush=True,
        )
    return durations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--table-sizes",
        type=int,
        nargs="+",
        default=[1000, 10000, 50000],
    )
    parser.add_argument(
        "--affected-counts",
        type=int,
        nargs="+",
        default=[100, 1000, 10000],
    )
    parser.add_argument(
        "--field-counts",
        type=int,
        nargs="+",
        default=[1, 3],
    )
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument(
        "--out", type=Path, default=Path("tasks/fts-sync-bench.json")
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Path to an existing codex sqlite3 DB to use as the bench "
        "snapshot. Skips migrate + seed; --table-sizes is ignored.",
    )
    args = parser.parse_args()

    db_path = _TMP_DIR / "codex.sqlite3"
    snap_path = _TMP_DIR / "snapshot.sqlite3"
    print(f"bench DB: {db_path}", flush=True)

    sweep_fields = tuple(COMICFTS_UPDATE_FIELDS)
    results: list[dict[str, Any]] = []

    if args.snapshot is not None:
        print(f"\n=== real snapshot: {args.snapshot} ===", flush=True)
        table_size = _setup_from_snapshot(args.snapshot, db_path, snap_path)
        print(f"  ComicFTS rows: {table_size:,}", flush=True)
        rng_pks = random.Random(0xC0DE)
        for n_affected in args.affected_counts:
            if n_affected > table_size:
                print(f"  skip affected={n_affected:,} (> table size)")
                continue
            chosen = _real_pks(rng_pks, n_affected)
            for n_fields in args.field_counts:
                if n_fields > len(sweep_fields):
                    continue
                fields = sweep_fields[:n_fields]
                print(
                    f"\n  combo: affected={n_affected:,} fields={n_fields}",
                    flush=True,
                )
                rng = random.Random(0xBEEF)
                durations = _run_combo_real(
                    db_path=db_path,
                    snap_path=snap_path,
                    chosen_pks=chosen,
                    fields=fields,
                    runs=args.runs,
                    rng=rng,
                )
                medians = {n: statistics.median(d) for n, d in durations.items()}
                results.append(
                    {
                        "table_size": table_size,
                        "n_affected": n_affected,
                        "n_fields": n_fields,
                        "medians_s": medians,
                        "all_runs_s": durations,
                        "source": "real",
                    }
                )
                ms = " ".join(
                    f"{n}={medians[n] * 1000:.0f}ms" for n in _STRATEGIES
                )
                print(f"    median: {ms}", flush=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=2))
        print(f"\nWrote {len(results)} combos to {args.out}", flush=True)
        return 0

    for table_size in args.table_sizes:
        print(f"\n=== table_size={table_size:,} ===", flush=True)
        _setup_one_size(table_size, db_path, snap_path)

        for n_affected in args.affected_counts:
            if n_affected > table_size:
                continue
            for n_fields in args.field_counts:
                if n_fields > len(sweep_fields):
                    continue
                fields = sweep_fields[:n_fields]
                print(
                    f"\n  combo: affected={n_affected:,} fields={n_fields}",
                    flush=True,
                )
                rng = random.Random(0xBEEF)
                durations = _run_combo(
                    db_path=db_path,
                    snap_path=snap_path,
                    table_size=table_size,
                    n_affected=n_affected,
                    fields=fields,
                    runs=args.runs,
                    rng=rng,
                )
                medians = {n: statistics.median(d) for n, d in durations.items()}
                row = {
                    "table_size": table_size,
                    "n_affected": n_affected,
                    "n_fields": n_fields,
                    "medians_s": medians,
                    "all_runs_s": durations,
                }
                results.append(row)
                ms = " ".join(
                    f"{n}={medians[n] * 1000:.0f}ms" for n in _STRATEGIES
                )
                print(f"    median: {ms}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {len(results)} combos to {args.out}", flush=True)

    # Summary table.
    print("\n=== Summary (median ms; lower is better) ===")
    print(
        f"{'table':>8} {'affected':>10} {'fields':>7} "
        + " ".join(f"{n:>16}" for n in _STRATEGIES)
    )
    for row in results:
        print(
            f"{row['table_size']:>8,} {row['n_affected']:>10,} "
            f"{row['n_fields']:>7} "
            + " ".join(
                f"{row['medians_s'][n] * 1000:>14.0f}ms" for n in _STRATEGIES
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
