"""Start and stop daemons."""
import asyncio
import threading

from codex.logger_base import LoggerBaseMixin
from codex.signals.os_signals import bind_signals_to_loop
from codex.websockets.listener import BroadcastListener


class LifespanApplication(LoggerBaseMixin):
    """Lifespan AGSI App."""

    SCOPE_TYPE = "lifespan"

    def __init__(self, log_queue, broadcast_queue):
        """Create logger and librarian."""
        self.init_logger(log_queue)
        self.broadcast_listener = BroadcastListener(broadcast_queue, log_queue)

    def release_thread_locks(self):
        """Release leaked, stuck thread locks."""
        # TODO unused remove :) :) :)
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

    async def _event(self, event, send):
        """Process a lifespan event."""
        try:
            self.log.debug(f"Lifespan {event} started.")
            func = getattr(self, "_" + event)
            await func()
            await send({"type": f"lifespan.{event}.complete"})
            self.log.debug(f"Lifespan {event} complete.")
        except Exception as exc:
            await send({"type": f"lifespan.{event}.failed"})
            self.log.error(f"Lifespan {event} failed.")
            raise exc

    async def _startup(self):
        """Startup tasks."""
        bind_signals_to_loop()
        self.broadcast_listener_task = asyncio.create_task(
            self.broadcast_listener.listen()
        )

    async def _shutdown(self):
        """Shutdown tasks."""
        await self.broadcast_listener_task

    async def __call__(self, scope, receive, send):
        """Lifespan application."""
        if scope["type"] != self.SCOPE_TYPE:
            return
        self.log.debug("Lifespan application started.")
        while True:
            try:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await self._event("startup", send)
                elif message["type"] == "lifespan.shutdown":
                    await self._event("shutdown", send)
                    break
            except Exception as exc:
                self.log.exception(exc)
        self.log.debug("Lifespan application stopped.")
