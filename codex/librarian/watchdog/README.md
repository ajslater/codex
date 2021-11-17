# Watchdog

Extends the Watchdog API with custom Observers, DirSnapshot, Emitter.
The Observers determine whether or not to watch different paths by querying the Library objects.
A CodexDatabaseSnapshot exists to compare the codex database against a standard DirSnapshot
Events are batched into large tasks for the Updater by the EventBatcher. The Emitter could do this more efficiently, but I'm also using the standard FileSystemObserver that spits them into a queue.

https://github.com/gorakhargosh/watchdog
