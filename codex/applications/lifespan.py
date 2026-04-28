"""Start and stop daemons."""

import asyncio
from contextlib import suppress

from loguru import logger

from codex.signals.os_signals import bind_signals_to_loop
from codex.startup.loguru import loguru_init
from codex.websockets.listener import BroadcastListener


class LifespanApplication:
    """Lifespan AGSI App."""

    SCOPE_TYPE = "lifespan"

    def __init__(self, broadcast_queue) -> None:
        """Create logger and librarian."""
        loguru_init()
        self.broadcast_queue = broadcast_queue
        self.broadcast_listener = BroadcastListener(logger, broadcast_queue)
        self.broadcast_listener_task = None

    async def _event(self, event, send) -> None:
        """Process a lifespan event."""
        try:
            logger.debug(f"Lifespan {event} started.")
            func = getattr(self, "_" + event)
            await func()
            await send({"type": f"lifespan.{event}.complete"})
            logger.debug(f"Lifespan {event} complete.")
        except Exception:
            await send({"type": f"lifespan.{event}.failed"})
            logger.exception(f"Lifespan {event} failed.")
            raise

    async def _startup(self) -> None:
        """Startup tasks."""
        bind_signals_to_loop()
        self.broadcast_listener_task = asyncio.create_task(
            self.broadcast_listener.listen()
        )

    async def _shutdown(self) -> None:
        """Shutdown tasks."""
        with suppress(ValueError):
            # Depending on timing this can be closed already
            self.broadcast_queue.put(None)
        if self.broadcast_listener_task:
            await self.broadcast_listener_task

    async def __call__(self, scope, receive, send) -> None:
        """Lifespan application."""
        if scope["type"] != self.SCOPE_TYPE:
            return
        logger.debug("Lifespan application started.")
        while True:
            try:
                message = await receive()
                match message["type"]:
                    case "lifespan.startup":
                        await self._event("startup", send)
                    case "lifespan.shutdown":
                        await self._event("shutdown", send)
                        break
            except Exception:
                logger.exception("Lifespan application")
        logger.debug("Lifespan application stopped.")
