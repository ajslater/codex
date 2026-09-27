/*
 * probeCover waits for a Codex cover the cover thread has not written yet.
 *
 * The cover endpoint answers 202 + Retry-After while it generates the
 * thumb, and an <img> cannot tell that from a 404. The probe can, and its
 * outcome decides whether the caller renders the image, keeps waiting, or
 * shows a placeholder. It must never fetch again once aborted: the review
 * dialog tears rows down whenever a panel closes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { COVER_PROBE, probeCover } from "@/api/v4/cover-probe";

const SRC = "/api/v4/covers/comic/123?ts=1726999999000";
const MAX_RETRIES = 5;
const HTTP_OK = 200;
const HTTP_ACCEPTED = 202;
const HTTP_NOT_FOUND = 404;
const HTTP_SERVER_ERROR = 500;

let fetchMock;

const respond = (status, headers = {}) =>
  new Response(null, { status, headers });

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("probeCover", () => {
  it("is READY after one fetch when the cover exists", async () => {
    fetchMock.mockResolvedValueOnce(respond(HTTP_OK));

    await expect(probeCover(SRC)).resolves.toBe(COVER_PROBE.READY);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      SRC,
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("is MISSING after one fetch on a 404", async () => {
    fetchMock.mockResolvedValueOnce(respond(HTTP_NOT_FOUND));

    await expect(probeCover(SRC)).resolves.toBe(COVER_PROBE.MISSING);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("waits out Retry-After on a 202, then is READY", async () => {
    fetchMock
      .mockResolvedValueOnce(respond(HTTP_ACCEPTED, { "Retry-After": "3" }))
      .mockResolvedValueOnce(respond(HTTP_OK));

    const result = probeCover(SRC);
    await vi.advanceTimersByTimeAsync(2999);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);

    await expect(result).resolves.toBe(COVER_PROBE.READY);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("waits the 2 s default when a 202 has no Retry-After", async () => {
    fetchMock
      .mockResolvedValueOnce(respond(HTTP_ACCEPTED))
      .mockResolvedValueOnce(respond(HTTP_OK));

    const result = probeCover(SRC);
    await vi.advanceTimersByTimeAsync(1999);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);

    await expect(result).resolves.toBe(COVER_PROBE.READY);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives up as PENDING after exactly maxRetries 202s", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(respond(HTTP_ACCEPTED)));

    const result = probeCover(SRC);
    await vi.runAllTimersAsync();

    await expect(result).resolves.toBe(COVER_PROBE.PENDING);
    expect(fetchMock).toHaveBeenCalledTimes(MAX_RETRIES);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("is ERROR when the fetch itself fails", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(probeCover(SRC)).resolves.toBe(COVER_PROBE.ERROR);
  });

  it("is ERROR on an unexpected status", async () => {
    fetchMock.mockResolvedValueOnce(respond(HTTP_SERVER_ERROR));

    await expect(probeCover(SRC)).resolves.toBe(COVER_PROBE.ERROR);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("stops without another fetch when aborted mid-wait", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(respond(HTTP_ACCEPTED)));
    const controller = new AbortController();

    const result = probeCover(SRC, { signal: controller.signal });
    await vi.advanceTimersByTimeAsync(1000);
    controller.abort();

    await expect(result).resolves.toBe(COVER_PROBE.ERROR);
    await vi.runAllTimersAsync();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal);
    expect(vi.getTimerCount()).toBe(0);
  });
});
