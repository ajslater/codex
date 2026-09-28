/*
 * loadGlobalSettings resolves after the settings land.
 *
 * It used to start its request in a fire-and-forget IIFE and resolve at
 * once, so reloadOnDefaultsChange, which awaits it when the admin defaults
 * change under an open reader, returned before the new settings arrived.
 */
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as READER_API from "@/api/v4/reader";
import { useAuthStore } from "@/stores/auth";
import { useReaderStore } from "@/stores/reader";
import { reloadOnDefaultsChange } from "@/stores/socket";

const GLOBAL = Object.freeze({
  data: { scopes: { global: { fitTo: "O" } } },
});

// A response that arrives after a real turn of the event loop.
const slowResponse = () =>
  new Promise((resolve) => {
    setTimeout(() => resolve(GLOBAL), 0);
  });

const settle = () =>
  new Promise((resolve) => {
    setTimeout(resolve, 0);
  });

describe("loadGlobalSettings", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("resolves only once the global settings have landed", async () => {
    const { promise, resolve } = Promise.withResolvers();
    vi.spyOn(READER_API, "getSettings").mockReturnValue(promise);
    const store = useReaderStore();
    let isSettled = false;

    const loading = (async () => {
      await store.loadGlobalSettings();
      isSettled = true;
    })();
    await settle();

    expect(isSettled).toBe(false);

    resolve(GLOBAL);
    await loading;

    expect(store.globalLoaded).toBe(true);
    expect(store.globalSettings.fitTo).toBe("O");
  });

  it("resolves after logging a failed load", async () => {
    vi.spyOn(READER_API, "getSettings").mockRejectedValue(new Error("down"));
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const store = useReaderStore();

    await store.loadGlobalSettings();

    expect(error).toHaveBeenCalledOnce();
    expect(store.globalLoaded).toBe(false);
  });

  it("lets a defaults change on the reader route wait for the new settings", async () => {
    const auth = useAuthStore();
    auth.defaultsRev = "r1";
    vi.spyOn(auth, "loadAdminFlags").mockImplementation(async () => {
      auth.defaultsRev = "r2";
    });
    vi.spyOn(READER_API, "getSettings").mockImplementation(slowResponse);
    const reader = useReaderStore();

    await expect(reloadOnDefaultsChange("reader")).resolves.toBe(true);

    expect(reader.globalLoaded).toBe(true);
    expect(reader.globalSettings.fitTo).toBe("O");
  });
});
