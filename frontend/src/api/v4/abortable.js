/*
 * Helpers for cancelling stale in-flight requests and deduplicating
 * concurrent identical fetches.
 */

const _controllers = new Map();
const _pending = new Map();

export function useAbortable(key) {
  const previous = _controllers.get(key);
  if (previous) previous.abort();
  const controller = new AbortController();
  _controllers.set(key, controller);
  return controller.signal;
}

export function abortKey(key) {
  const controller = _controllers.get(key);
  if (!controller) return false;
  controller.abort();
  _controllers.delete(key);
  return true;
}

export function isAbortError(error) {
  if (!error) return false;
  return error.name === "AbortError" || error.name === "CanceledError";
}

export function dedupedFetch(key, fetcher) {
  const existing = _pending.get(key);
  if (existing) return existing;
  const promise = Promise.resolve()
    .then(fetcher)
    .finally(() => _pending.delete(key));
  _pending.set(key, promise);
  return promise;
}
