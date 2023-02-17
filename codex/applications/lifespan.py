"""Start and stop daemons."""
import threading

from codex.logger_base import LoggerBaseMixin
from codex.signals.os_signals import bind_signals_to_loop


class LifespanApplication(LoggerBaseMixin):
    """Lifespan AGSI App."""

    SCOPE_TYPE = "lifespan"

    def __init__(self, log_queue):
        """Create logger and librarian."""
        self.init_logger(log_queue)

    def release_thread_locks(self):
        """
        Release leaked, stuck thread locks.

        For an unknown reason more than one simultaneous consumer leads to
        a thread hanging and prevent codex from exiting. I'm not cleaning up
        something somewhere.
        """
        released = 0
        for thread in threading.enumerate():
            if thread.name.startswith("ThreadPoolExecutor"):
                lock = getattr(thread, "_tstate_lock", None)
                if lock:
                    lock.release()  # type: ignore
                    thread._stop()  # type: ignore
                    released += 1
        if released:
            self.log.debug(f"Released {released} locked threads.")
        else:
            self.log.info("No locked threads to clean up :)")

    async def __call__(self, scope, receive, send):
        """Lifespan application."""
        if scope["type"] != self.SCOPE_TYPE:
            return
        self.log.debug("Lifespan application started.")
        while True:
            try:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    try:
                        bind_signals_to_loop()
                        await send({"type": "lifespan.startup.complete"})
                        self.log.debug("Lifespan startup complete.")
                    except Exception as exc:
                        await send({"type": "lifespan.startup.failed"})
                        self.log.error("Lifespan startup failed.")
                        raise exc
                elif message["type"] == "lifespan.shutdown":
                    self.log.debug("Lifespan shutdown started.")
                    try:
                        self.release_thread_locks()
                        await send({"type": "lifespan.shutdown.complete"})
                        self.log.debug("Lifespan shutdown complete.")
                    except Exception as exc:
                        await send({"type": "lifespan.shutdown.failed"})
                        self.log.error("Lifespan shutdown failed.")
                        raise exc
                    break
            except Exception as exc:
                self.log.exception(exc)
        self.log.debug("Lifespan application stopped.")
