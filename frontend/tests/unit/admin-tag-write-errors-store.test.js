/*
 * Spec for the order the admin store's tag-write errors land in. The
 * Tagging tab and the settings button read the list unforced when they
 * mount, and the WebSocket forces a reload whenever it changes, so reads
 * overlap. clearTagWriteErrors is ordered with those reads.
 *
 * The HTTP layer is mocked. Deferred promises hold responses open so each
 * case picks the order they land in.
 */
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock(import("@/api/v4/admin"), async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    clearTagWriteErrors: vi.fn(),
    getTagWriteErrors: vi.fn(),
  };
});

import * as API from "@/api/v4/admin";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

const NOW = Date.UTC(2026, 0, 1);
const LATER = NOW + 1000;
const TTL_MS = 5000;

const errorsFor = (version) => [
  { error: `failed ${version}`, path: `/comics/${version}.cbz`, time: "" },
];

// Hold the next read open; the returned function lands it.
const deferRead = () => {
  const response = Promise.withResolvers();
  API.getTagWriteErrors.mockReturnValueOnce(response.promise);
  return (version) => response.resolve({ data: errorsFor(version) });
};

// Hold the next clear open; the returned function lands it.
const deferClear = () => {
  const response = Promise.withResolvers();
  API.clearTagWriteErrors.mockReturnValueOnce(response.promise);
  return () => response.resolve({ data: { detail: "cleared" } });
};

const advance = (ms) => vi.setSystemTime(Date.now() + ms);

function adminStore() {
  useAuthStore().user = { id: 1, isStaff: true, username: "admin" };
  return useAdminStore();
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  API.getTagWriteErrors.mockReset();
  API.clearTagWriteErrors.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("loadTagWriteErrors response order", () => {
  it("drops a slow mount read that lands after a WebSocket reload", async () => {
    const landMount = deferRead();
    const landSocket = deferRead();
    const store = adminStore();
    // The Tagging tab mounts with an empty cache; its read stalls.
    const mountRead = store.loadTagWriteErrors();
    // A tag write fails and the WebSocket forces a reload that lands first.
    vi.setSystemTime(LATER);
    const socketRead = store.loadTagWriteErrors({ force: true });
    landSocket(2);
    await socketRead;
    advance(500);
    landMount(1);
    await mountRead;

    expect(store.tagWriteErrors).toStrictEqual(errorsFor(2));
    expect(store.timestamps.TagWriteErrors).toBe(LATER);

    // An unforced read inside the reload's TTL is served its errors.
    vi.setSystemTime(LATER + TTL_MS - 1);
    await store.loadTagWriteErrors();

    expect(API.getTagWriteErrors).toHaveBeenCalledTimes(2);
    expect(store.tagWriteErrors).toStrictEqual(errorsFor(2));
  });

  it("lands both reads when they arrive in order", async () => {
    const landMount = deferRead();
    const landSocket = deferRead();
    const store = adminStore();
    const mountRead = store.loadTagWriteErrors();
    vi.setSystemTime(LATER);
    const socketRead = store.loadTagWriteErrors({ force: true });

    landMount(1);
    await mountRead;
    expect(store.tagWriteErrors).toStrictEqual(errorsFor(1));
    expect(store.timestamps.TagWriteErrors).toBe(NOW);

    landSocket(2);
    await socketRead;
    expect(store.tagWriteErrors).toStrictEqual(errorsFor(2));
    expect(store.timestamps.TagWriteErrors).toBe(LATER);
  });

  it("still lands an earlier read when the later one fails", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const landMount = deferRead();
    API.getTagWriteErrors.mockRejectedValueOnce(new Error("offline"));
    const store = adminStore();
    const mountRead = store.loadTagWriteErrors();
    await store.loadTagWriteErrors({ force: true });

    landMount(1);
    await mountRead;

    expect(store.tagWriteErrors).toStrictEqual(errorsFor(1));
    expect(store.timestamps.TagWriteErrors).toBe(NOW);
  });

  it("stamps the time the read went out, not when it landed", async () => {
    const land = deferRead();
    const store = adminStore();
    const read = store.loadTagWriteErrors();
    advance(3000);
    land(1);
    await read;

    expect(store.timestamps.TagWriteErrors).toBe(NOW);

    // The TTL runs from the request, so it is over TTL_MS after it went out.
    vi.setSystemTime(NOW + TTL_MS);
    API.getTagWriteErrors.mockResolvedValueOnce({ data: errorsFor(2) });
    await store.loadTagWriteErrors();

    expect(API.getTagWriteErrors).toHaveBeenCalledTimes(2);
    expect(store.tagWriteErrors).toStrictEqual(errorsFor(2));
  });
});

describe("clearTagWriteErrors order", () => {
  it("drops a read that went out before the clear and lands after it", async () => {
    const landMount = deferRead();
    const landClear = deferClear();
    const store = adminStore();
    const mountRead = store.loadTagWriteErrors();
    vi.setSystemTime(LATER);
    const clear = store.clearTagWriteErrors();
    landClear();
    await clear;
    advance(500);
    landMount(1);
    await mountRead;

    expect(store.tagWriteErrors).toStrictEqual([]);
    expect(store.timestamps.TagWriteErrors).toBe(LATER);
  });

  it("is dropped when a read that went out after it already landed", async () => {
    const landClear = deferClear();
    const landSocket = deferRead();
    const store = adminStore();
    store.tagWriteErrors = errorsFor(1);
    const clear = store.clearTagWriteErrors();
    // The clear's broadcast reload goes out and lands a fresh error first.
    vi.setSystemTime(LATER);
    const socketRead = store.loadTagWriteErrors({ force: true });
    landSocket(2);
    await socketRead;
    landClear();
    await clear;

    expect(store.tagWriteErrors).toStrictEqual(errorsFor(2));
    expect(store.timestamps.TagWriteErrors).toBe(LATER);
  });

  it("lets a read that went out after it land later", async () => {
    const landClear = deferClear();
    const landSocket = deferRead();
    const store = adminStore();
    store.tagWriteErrors = errorsFor(1);
    const clear = store.clearTagWriteErrors();
    vi.setSystemTime(LATER);
    const socketRead = store.loadTagWriteErrors({ force: true });

    landClear();
    await clear;
    expect(store.tagWriteErrors).toStrictEqual([]);
    expect(store.timestamps.TagWriteErrors).toBe(NOW);

    landSocket(2);
    await socketRead;
    expect(store.tagWriteErrors).toStrictEqual(errorsFor(2));
    expect(store.timestamps.TagWriteErrors).toBe(LATER);
  });

  it("still lands an earlier read when the clear fails", async () => {
    const landMount = deferRead();
    API.clearTagWriteErrors.mockRejectedValueOnce(new Error("offline"));
    const store = adminStore();
    const mountRead = store.loadTagWriteErrors();
    await store.clearTagWriteErrors();

    landMount(1);
    await mountRead;

    expect(store.tagWriteErrors).toStrictEqual(errorsFor(1));
    expect(store.timestamps.TagWriteErrors).toBe(NOW);
  });
});
