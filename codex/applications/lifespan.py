"""Start and stop daemons."""
from wsproto.frame_protocol import CloseReason

from codex.logger_base import LoggerBaseMixin
from codex.signals.os_signals import bind_signals_to_loop


WS_DISCONNECT_MESSAGE = {
    "type": "websocket_disconnect",
    "code": CloseReason.NORMAL_CLOSURE,
}


class LifespanApplication(LoggerBaseMixin):
    """Lifespan AGSI App."""

    SCOPE_TYPE = "lifespan"

    def __init__(self, log_queue):
        """Create logger and librarian."""
        self.init_logger(log_queue)

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
