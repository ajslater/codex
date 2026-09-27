/*
 * Probe a Codex cover URL until the thumb exists.
 *
 * The cover endpoint answers 202 Accepted with Retry-After while the cover
 * thread is still generating the thumb, and that same GET is what queues the
 * generation. An <img> reports a 202 and a 404 identically, as an error, so a
 * caller that has to wait for a cover probes it with fetch first and renders
 * the <img> once the probe says READY.
 *
 * book-cover.vue still carries its own copy of this loop.
 */
export const COVER_PROBE = Object.freeze({
  READY: "ready",
  MISSING: "missing",
  PENDING: "pending",
  ERROR: "error",
});

const HTTP_ACCEPTED = 202;
const HTTP_NOT_FOUND = 404;
const MS_PER_SEC = 1000;

function sleep(ms, signal) {
  // Rejects on abort so a probe torn down mid-wait never fetches again.
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason);
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function retryAfterMs(response, defaultRetryAfterSec) {
  const seconds = Number.parseInt(response.headers.get("Retry-After"), 10);
  return (seconds > 0 ? seconds : defaultRetryAfterSec) * MS_PER_SEC;
}

/*
 * Resolve to one COVER_PROBE value; never rejects. A 2xx other than 202 is
 * READY, a 404 is MISSING, and `maxRetries` 202s in a row are PENDING. Any
 * other status, a network failure or an abort is ERROR.
 */
export async function probeCover(
  src,
  { signal, maxRetries = 5, defaultRetryAfterSec = 2 } = {},
) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    let response;
    try {
      response = await fetch(src, { credentials: "same-origin", signal });
    } catch {
      return COVER_PROBE.ERROR;
    }
    if (response.status === HTTP_NOT_FOUND) return COVER_PROBE.MISSING;
    if (response.status !== HTTP_ACCEPTED) {
      return response.ok ? COVER_PROBE.READY : COVER_PROBE.ERROR;
    }
    if (attempt === maxRetries) break;
    try {
      await sleep(retryAfterMs(response, defaultRetryAfterSec), signal);
    } catch {
      return COVER_PROBE.ERROR;
    }
  }
  return COVER_PROBE.PENDING;
}
