"""
A fixed pool of long-lived thread-sensitive workers for HTTP requests.

Django's ``ASGIHandler`` enters an asgiref ``ThreadSensitiveContext`` per
request, and asgiref backs each context with a private one-thread
executor it shuts down when the context exits. Every request therefore
gets a brand new thread, and since ``django.db.connections`` is
thread-local, a brand new database connection — which is why Django
documents that persistent connections do not work under ASGI.

This pool owns a fixed number of contexts that are *never* entered,
pre-seeds each with its own one-thread executor, and lends one to each
request. The worker thread, and the connection it holds, outlive the
request, which restores the stable-thread model ``CONN_MAX_AGE`` was
written for. Django's own ``request_started`` / ``request_finished``
hygiene then recycles those connections exactly as it does under WSGI.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final

from asgiref.sync import SyncToAsync, ThreadSensitiveContext, sync_to_async
from django.db import connections
from loguru import logger

from codex.librarian.db import enable_persistent_connections
from codex.settings import DB_WORKERS

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Iterable

_THREAD_NAME_PREFIX: Final[str] = "codex-http-db"
# Seconds to wait for the pooled worker to answer the startup self-check.
_SELF_CHECK_TIMEOUT: Final[float] = 5.0


class WorkerPool:
    """A fixed set of pooled ``ThreadSensitiveContext`` workers."""

    # Seconds to wait at shutdown for in-flight requests to hand back
    # their worker before closing connections out from under them.
    STOP_TIMEOUT: Final[float] = 10.0

    def __init__(self, size: int) -> None:
        """Size the pool. Nothing is created until ``start``."""
        self.size = max(0, int(size))
        self.enabled = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._free: asyncio.LifoQueue[ThreadSensitiveContext] | None = None
        self._contexts: tuple[ThreadSensitiveContext, ...] = ()
        self._executors: dict[ThreadSensitiveContext, ThreadPoolExecutor] = {}

    async def _run_on(self, context: ThreadSensitiveContext, func: Callable) -> None:
        """Run ``func`` on ``context``'s worker thread."""
        token = SyncToAsync.thread_sensitive_context.set(context)
        try:
            await sync_to_async(func)()
        finally:
            SyncToAsync.thread_sensitive_context.reset(token)

    async def _self_check(self) -> bool:
        """
        Prove asgiref still routes onto the thread we seeded.

        The pool reaches into two of asgiref's class attributes to
        install a context the way asgiref would have installed it
        lazily. They have been stable for years but are not part of a
        documented contract, so rather than trust them, check them: run
        the exact shape a request will (Django's own inner
        ``ThreadSensitiveContext``, two thread-sensitive calls) and
        confirm both land on the seeded worker. A failure here disables
        the pool rather than silently serving requests on the wrong
        thread.
        """
        context = self._contexts[0]
        try:
            expected = (
                self._executors[context]
                .submit(threading.get_ident)
                .result(_SELF_CHECK_TIMEOUT)
            )
            token = SyncToAsync.thread_sensitive_context.set(context)
            try:
                async with ThreadSensitiveContext():
                    first = await sync_to_async(threading.get_ident)()
                    second = await sync_to_async(threading.get_ident)()
            finally:
                SyncToAsync.thread_sensitive_context.reset(token)
        except Exception:
            logger.exception("HTTP database worker pool self-check failed")
            return False
        return (
            first == expected
            and second == expected
            and context in SyncToAsync.context_to_thread_executor
        )

    async def start(self) -> None:
        """Create the workers on the running loop. Idempotent per loop."""
        loop = asyncio.get_running_loop()
        if self._free is not None:
            if self._loop is loop:
                return
            # A previous loop owned it. Only reachable under tests.
            await self.stop()
        if not self.size:
            logger.debug("HTTP database worker pool disabled.")
            return
        contexts = []
        for index in range(self.size):
            context = ThreadSensitiveContext()
            executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix=f"{_THREAD_NAME_PREFIX}-{index}"
            )
            # The write asgiref would make lazily on the first
            # thread-sensitive call inside this context. Making it here
            # is what pins the context to a thread we own and can join.
            SyncToAsync.context_to_thread_executor[context] = executor
            self._executors[context] = executor
            contexts.append(context)
        self._contexts = tuple(contexts)
        if not await self._self_check():
            reason = (
                "asgiref no longer routes thread-sensitive work onto pooled workers."
            )
            reason += " Serving requests on per-request threads instead."
            logger.warning(reason)
            await self._retire(self._contexts)
            self._reset()
            return
        # Safe only now that requests land on threads that outlive them.
        enable_persistent_connections()
        self._loop = loop
        free: asyncio.LifoQueue[ThreadSensitiveContext] = asyncio.LifoQueue()
        for context in self._contexts:
            free.put_nowait(context)
        self._free = free
        self.enabled = True
        logger.debug(f"HTTP database worker pool started with {self.size} workers.")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[None]:
        """
        Lend a worker to one request for its whole duration.

        Waiting for a free worker happens on the event loop and costs no
        thread. Holding the worker across the whole request — not just
        its ORM calls — is what bounds concurrency: a request keeps its
        database connection, and its share of the page cache, from its
        first query until its response is sent.
        """
        free = self._free
        if free is None:
            msg = "Worker pool is not started."
            raise RuntimeError(msg)
        context = await free.get()
        token = SyncToAsync.thread_sensitive_context.set(context)
        try:
            yield
        finally:
            SyncToAsync.thread_sensitive_context.reset(token)
            # Hand the worker back to the queue it came from, which may
            # no longer be the pool's: a request that outlasts
            # ``STOP_TIMEOUT`` returns its worker after shutdown has
            # already stopped waiting for it.
            free.put_nowait(context)

    async def _retire(
        self,
        idle: Iterable[ThreadSensitiveContext],
        busy: Iterable[ThreadSensitiveContext] = (),
    ) -> None:
        """Close each worker's connections, then join its thread."""
        for context in idle:
            await self._run_on(context, connections.close_all)
        for context in busy:
            # A one-thread executor runs this after the in-flight
            # request finishes with the worker.
            self._executors[context].submit(connections.close_all)
        for context in self._contexts:
            SyncToAsync.context_to_thread_executor.pop(context, None)
        await _join(tuple(self._executors.values()))

    async def stop(self) -> None:
        """Take the pool out of service and release its workers."""
        if self._free is None:
            return
        self.enabled = False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.STOP_TIMEOUT
        idle: list[ThreadSensitiveContext] = []
        while len(idle) < len(self._contexts):
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                idle.append(await asyncio.wait_for(self._free.get(), remaining))
            except TimeoutError:
                break
        busy = [context for context in self._contexts if context not in idle]
        if busy:
            logger.warning(
                f"{len(busy)} HTTP database worker(s) still busy at shutdown."
            )
        await self._retire(idle, busy)
        self._reset()
        logger.debug("HTTP database worker pool stopped.")

    def _reset(self) -> None:
        """Drop every reference to the retired workers."""
        self.enabled = False
        self._loop = None
        self._free = None
        self._contexts = ()
        self._executors = {}


async def _join(executors: tuple[ThreadPoolExecutor, ...]) -> None:
    """
    Join worker threads without blocking the event loop.

    A worker may itself be parked waiting on this loop, so a blocking
    ``shutdown()`` here would deadlock it — the same hazard asgiref
    handles in ``ThreadSensitiveContext.__aexit__``. The loop's default
    executor is no good either: work queued there may be what unparks
    the worker. So join in a thread of our own.
    """
    if not executors:
        return
    done: Future[None] = Future()

    def join() -> None:
        try:
            for executor in executors:
                executor.shutdown()
        except Exception as exc:  # pragma: no cover - defensive
            done.set_exception(exc)
        else:
            done.set_result(None)

    threading.Thread(target=join, daemon=True).start()
    await asyncio.wrap_future(done)


WORKER_POOL: Final[WorkerPool] = WorkerPool(DB_WORKERS)
