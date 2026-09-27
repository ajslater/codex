/*
 * Unit tests for the admin store's site-defaults actions:
 * loadSettingsDefaults (TTL-gated), updateSettingsDefaults (with and
 * without the catch-up) and loadSettingsDefaultsReach (never cached).
 * HTTP layer mocked; admin gate driven through the auth store.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock(import("@/api/v4/admin"), async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    getSettingsDefaults: vi.fn(),
    updateSettingsDefaults: vi.fn(),
    getSettingsDefaultsReach: vi.fn(),
  };
});

import * as API from "@/api/v4/admin";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const PAYLOAD = Object.freeze({
  browser: { topCollection: "folders", bookmark: "UNREAD" },
  reader: { fitTo: "H" },
  factory: { browser: { topCollection: "publishers" }, reader: {} },
});

function adminStore() {
  const authStore = useAuthStore();
  authStore.user = { id: 1, username: "admin", isStaff: true };
  return useAdminStore();
}

beforeEach(() => {
  setActivePinia(createPinia());
  for (const fn of Object.values(API)) {
    if (typeof fn?.mockReset === "function") {
      fn.mockReset();
    }
  }
});

describe("loadSettingsDefaults", () => {
  it("loads once, then serves the cache inside the TTL", async () => {
    API.getSettingsDefaults.mockResolvedValue({ data: PAYLOAD });
    const store = adminStore();
    await store.loadSettingsDefaults();
    await store.loadSettingsDefaults();
    expect(API.getSettingsDefaults).toHaveBeenCalledTimes(1);
    expect(store.settingsDefaults).toEqual(PAYLOAD);
  });

  it("refetches when forced", async () => {
    API.getSettingsDefaults.mockResolvedValue({ data: PAYLOAD });
    const store = adminStore();
    await store.loadSettingsDefaults();
    await store.loadSettingsDefaults({ force: true });
    expect(API.getSettingsDefaults).toHaveBeenCalledTimes(2);
  });

  it("does nothing for a non-admin", async () => {
    const store = useAdminStore();
    await store.loadSettingsDefaults();
    expect(API.getSettingsDefaults).not.toHaveBeenCalled();
  });
});

describe("updateSettingsDefaults", () => {
  it("PUTs the section without the catch-up flag by default", async () => {
    API.updateSettingsDefaults.mockResolvedValue({ data: PAYLOAD });
    const store = adminStore();
    const data = { browser: { viewMode: "table" } };
    const applied = await store.updateSettingsDefaults(data);
    expect(API.updateSettingsDefaults).toHaveBeenCalledWith(data);
    expect(applied).toEqual({});
    expect(store.settingsDefaults).toEqual(PAYLOAD);
  });

  it("sends applyToAnonymous and returns the applied counts", async () => {
    API.updateSettingsDefaults.mockResolvedValue({
      data: { ...PAYLOAD, applied: { viewMode: 3 } },
    });
    const store = adminStore();
    const data = { browser: { viewMode: "table" } };
    const applied = await store.updateSettingsDefaults(data, {
      applyToAnonymous: true,
    });
    expect(API.updateSettingsDefaults).toHaveBeenCalledWith({
      ...data,
      applyToAnonymous: true,
    });
    expect(applied).toEqual({ viewMode: 3 });
    // The counts are a response detail, not stored settings.
    expect(store.settingsDefaults).toEqual(PAYLOAD);
  });

  it("surfaces a 400 and resolves undefined", async () => {
    API.updateSettingsDefaults.mockRejectedValue({
      response: { data: { topCollection: ["hidden"] } },
    });
    const store = adminStore();
    const applied = await store.updateSettingsDefaults({ browser: {} });
    expect(applied).toBeUndefined();
    expect(useCommonStore().form.fieldErrors).toEqual({
      topCollection: ["hidden"],
    });
  });
});

describe("loadSettingsDefaultsReach", () => {
  it("fetches every time and returns the counts", async () => {
    API.getSettingsDefaultsReach.mockResolvedValue({ data: { viewMode: 4 } });
    const store = adminStore();
    expect(await store.loadSettingsDefaultsReach()).toEqual({ viewMode: 4 });
    await store.loadSettingsDefaultsReach();
    expect(API.getSettingsDefaultsReach).toHaveBeenCalledTimes(2);
  });
});
