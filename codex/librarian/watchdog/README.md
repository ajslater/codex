# Watchdog

- Extends the Watchdog API with custom Observers, DirSnapshot, Emitter.
- The Observers decide to watch different paths by querying the Library objects.
- A CodexDatabaseSnapshot exists to compare the codex database against a
  standard DirSnapshot
- Events batch into large tasks for the Updater by the EventBatcher. The Emitter
  could do this more efficiently, but I'm also using the standard
  FileSystemObserver that spits them into a queue.

[Watchdog project page](https://github.com/gorakhargosh/watchdog)
