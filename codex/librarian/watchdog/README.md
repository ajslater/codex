# Watchdog

Filesystem watching for Codex libraries using
[watchfiles](https://github.com/samuelcolvin/watchfiles) (Rust `notify` backend).

## Architecture

- **`watcher.py`** — `LibraryWatcherThread`: A single thread watches all
  event-enabled library paths using `watchfiles.watch()`. Multiple paths go
  into one `watch()` call, so N libraries = 1 watcher thread. When library
  config changes, the watch is restarted with updated paths.

- **`poller.py`** — `LibraryPollerThread`: Periodically compares database
  snapshots against disk snapshots to detect changes that filesystem events
  might miss (e.g. network mounts, Docker volumes).

- **`event_batcherd.py`** — `WatchdogEventBatcherThread`: Aggregates events
  from both the watcher and poller into batched `ImportTask` instances for
  the importer.

- **`handlers.py`** — Classifies raw filesystem changes into comic, cover,
  and directory events.

- **`snapshot.py`** / **`snapshot_diff.py`** — Standalone snapshot and diff
  classes for the poller. `DatabaseSnapshot` reads from Django ORM,
  `DiskSnapshot` walks the filesystem.

- **`events.py`** — Simple dataclasses for filesystem events and poll signals.
