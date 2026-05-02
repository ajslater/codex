# File System Watcher & Poller

Filesystem watching for Codex libraries using
[watchfiles](https://github.com/samuelcolvin/watchfiles) (Rust `notify`
backend).

## Architecture

- **`watcher`** — A single thread watches all event-enabled library paths using
  `watchfiles.watch()`. Multiple paths go into one `watch()` call, so N
  libraries = 1 watcher thread. When library config changes, the watch is
  restarted with updated paths. Watchfiles itself does the batching (`step` /
  `debounce` parameters): it yields after a quiet period, or once a hard cap on
  continuous activity is reached.

- **`poller`** — Periodically compares database snapshots against disk snapshots
  to detect changes that filesystem events might miss (e.g. network mounts,
  Docker volumes).

- **`import_task.py`** — `build_import_task()`: pure helper that takes a batch
  of `FSEvent`s for a single library, deduplicates conflicting events, and
  returns one `ImportTask` (or `None` if the batch is empty after dedup). Both
  the watcher and poller call this to emit `ImportTask`s directly to the scribe
  via the librarian queue.
