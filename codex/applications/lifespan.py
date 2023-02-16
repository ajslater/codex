"""Start and stop daemons."""
from wsproto.frame_protocol import CloseReason

from codex.librarian.librariand import LIBRARIAN_SHUTDOWN_TASK
from codex.logger_base import LoggerBaseMixin
from codex.signals.os_signals import bind_signals_to_loop


WS_DISCONNECT_MESSAGE = {
    "type": "websocket_disconnect",
    "code": CloseReason.NORMAL_CLOSURE,
}


class LifespanApplication(LoggerBaseMixin):
    """Lifespan AGSI App."""

    SCOPE_TYPE = "lifespan"

    def __init__(self, log_queue, librarian_queue, broadcast_queue):
        """Create logger and librarian."""
        self.init_logger(log_queue)
        self.librarian_queue = librarian_queue
        self.broadcast_queue = broadcast_queue

    async def codex_shutdown(self):
        """Send stop signals to daemon & consumers."""
        # item = NotifierConsumer.create_broadcast_group_item(
        #    ChannelGroups.ALL, WS_DISCONNECT_MESSAGE
        # )
        # self.broadcast_queue.coro_put(item)
        self.librarian_queue.put(LIBRARIAN_SHUTDOWN_TASK)
        print("SHUTDOWN")
        import threading

        for thread in threading.enumerate():
            if thread.name != "MainThread":
                print(thread.name, thread.is_alive())

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
                        await self.codex_shutdown()
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
