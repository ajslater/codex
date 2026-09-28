/*
 * Helpers for cancelling stale in-flight requests and deduplicating
 * concurrent identical fetches.
 */

const _controllers = new Map();
const _pending = new Map();

export function abortKey(key) {
  const controller = _controllers.get(key);
  if (!controller) return false;
  controller.abort();
  _controllers.delete(key);
  return true;
}

export function dedupedFetch(key, fetcher) {
  const existing = _pending.get(key);
  if (existing) return existing;
  const promise = runDeduped(key, fetcher);
  _pending.set(key, promise);
  return promise;
}

export function isAbortError(error) {
  return error
    ? error.name === "AbortError" || error.name === "CanceledError"
    : false;
}

export function useAbortable(key) {
  const previous = _controllers.get(key);
  if (previous) previous.abort();
  const controller = new AbortController();
  _controllers.set(key, controller);
  return controller.signal;
}

async function runDeduped(key, fetcher) {
  /*
   * Yield before calling the fetcher so dedupedFetch registers this
   * promise first. A fetcher that throws synchronously would otherwise
   * clean up before the entry exists and strand it in the map.
   */
  await Promise.resolve();
  try {
    return await fetcher();
  } finally {
    _pending.delete(key);
  }
}
