/*
 * Helpers for cancelling stale in-flight requests and deduplicating
 * concurrent identical fetches.
 *
 * ``useAbortable(key)`` — single-flight per key. Calling it again
 * with the same key aborts the previous AbortController and returns
 * a fresh signal. Adopt at API call sites where rapid user input
 * (rapid clicks, debounced filter changes) can fire overlapping
 * requests; the late-arriving response from a prior call is
 * effectively dropped because the caller's abort handler suppresses
 * it.
 *
 * ``dedupedFetch(key, fetcher)`` — same-key callers share an
 * in-flight promise rather than each firing their own request. Use
 * for read-only endpoints where multiple components want the same
 * data fast (mtime checks, choice menus). The cache clears on
 * settle so a stuck promise can't pin the dedup forever.
 */

const _controllers = new Map();
const _pending = new Map();

/**
 * Get an AbortSignal for the keyed request, aborting any prior one.
 *
 * @param {string} key Stable per-call-site identifier (e.g.
 *   ``"browser:loadBrowserPage"``). Two callers using the same key
 *   participate in the same single-flight slot.
 * @returns {AbortSignal}
 */
export function useAbortable(key) {
  const previous = _controllers.get(key);
  if (previous) previous.abort();
  const controller = new AbortController();
  _controllers.set(key, controller);
  return controller.signal;
}

/**
 * True if an error came from an aborted request.
 *
 * Both xior (CanceledError) and the platform fetch (AbortError)
 * surface the same intent under different names. Catch broadly and
 * suppress at the call site so the late-arriving aborted response
 * doesn't ``$patch`` stale state.
 */
export function isAbortError(error) {
  if (!error) return false;
  return error.name === "AbortError" || error.name === "CanceledError";
}

/**
 * Share an in-flight promise across same-key callers.
 *
 * @param {string} key Stable identifier shared by callers that want
 *   to coalesce.
 * @param {() => Promise<T>} fetcher Invoked only when no pending
 *   promise exists for ``key``.
 * @returns {Promise<T>}
 */
export function dedupedFetch(key, fetcher) {
  const existing = _pending.get(key);
  if (existing) return existing;
  const promise = Promise.resolve()
    .then(fetcher)
    .finally(() => _pending.delete(key));
  _pending.set(key, promise);
  return promise;
}
