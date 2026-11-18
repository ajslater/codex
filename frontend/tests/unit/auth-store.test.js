/*
 * Unit tests for the new auth-store actions added by the password-reset
 * feature: updateProfile, sendResetPasswordLink, resetPassword. Covers
 * the success and error paths plus the no-op short-circuit on an empty
 * profile diff. HTTP layer is mocked.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/v4/auth", () => ({
  getAdminFlags: vi.fn(),
  getSession: vi.fn(),
  updateTimezone: vi.fn(),
  register: vi.fn(),
  login: vi.fn(),
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
  logout: vi.fn(),
  updatePassword: vi.fn(),
  sendResetPasswordLink: vi.fn(),
  resetPassword: vi.fn(),
  getApiKeys: vi.fn(),
  createApiKey: vi.fn(),
  deleteApiKey: vi.fn(),
  getApiUrls: vi.fn(),
}));

import * as API from "@/api/v4/auth";
import { APIError } from "@/api/v4/base";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";
import { reloadOnDefaultsChange } from "@/stores/socket";

const DEFAULTS = Object.freeze({
  browser: { topCollection: "folders", bookmark: "UNREAD" },
  reader: { fitTo: "H" },
});

function sessionResponse(extra = {}) {
  return {
    data: { user: null, adminFlags: { nonUsers: true }, ...extra },
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  for (const fn of Object.values(API)) {
    if (typeof fn?.mockReset === "function") {
      fn.mockReset();
    }
  }
});

describe("useAuthStore — updateProfile", () => {
  it("short-circuits on an empty diff without touching the API", async () => {
    const store = useAuthStore();
    const ok = await store.updateProfile({});
    expect(ok).toBe(true);
    expect(API.updateProfile).not.toHaveBeenCalled();
  });

  it("PATCHes only the supplied fields and refreshes user state", async () => {
    API.updateProfile.mockResolvedValue({
      data: { username: "alice", email: "alice+new@example.com" },
    });
    const store = useAuthStore();
    const ok = await store.updateProfile({ email: "alice+new@example.com" });
    expect(ok).toBe(true);
    expect(API.updateProfile).toHaveBeenCalledWith({
      email: "alice+new@example.com",
    });
    expect(store.user).toEqual({
      username: "alice",
      email: "alice+new@example.com",
    });
  });

  it("surfaces API errors to commonStore and returns false", async () => {
    API.updateProfile.mockRejectedValue({
      response: { data: { username: ["already used"] } },
    });
    const store = useAuthStore();
    const ok = await store.updateProfile({ username: "taken" });
    expect(ok).toBe(false);
    const commonStore = useCommonStore();
    expect(commonStore.form.errors).toBeTruthy();
  });
});

describe("useAuthStore — sendResetPasswordLink", () => {
  it("posts the login string and sets the success banner", async () => {
    API.sendResetPasswordLink.mockResolvedValue({
      data: { detail: "Reset link sent" },
    });
    const store = useAuthStore();
    const ok = await store.sendResetPasswordLink("alice");
    expect(ok).toBe(true);
    expect(API.sendResetPasswordLink).toHaveBeenCalledWith("alice");
    // The green banner shown on the login screen comes from commonStore.
    expect(useCommonStore().form.success).toBe("Reset link sent");
  });

  it("returns false on error", async () => {
    API.sendResetPasswordLink.mockRejectedValue(new Error("boom"));
    const store = useAuthStore();
    const ok = await store.sendResetPasswordLink("alice");
    expect(ok).toBe(false);
  });
});

describe("useAuthStore — resetPassword", () => {
  it("forwards the signed payload and returns true on success", async () => {
    API.resetPassword.mockResolvedValue({
      data: { detail: "Reset password successful" },
    });
    const store = useAuthStore();
    const payload = {
      userId: "1",
      timestamp: 100,
      signature: "sig",
      password: "newpw",
    };
    const ok = await store.resetPassword(payload);
    expect(ok).toBe(true);
    expect(API.resetPassword).toHaveBeenCalledWith(payload);
  });

  it("returns false on rejection", async () => {
    API.resetPassword.mockRejectedValue(new Error("bad signature"));
    const store = useAuthStore();
    const ok = await store.resetPassword({
      userId: "1",
      timestamp: 100,
      signature: "bad",
      password: "newpw",
    });
    expect(ok).toBe(false);
  });
});

describe("useAuthStore — site defaults", () => {
  it("loadSession keeps defaults and defaultsRev", async () => {
    API.getSession.mockResolvedValue(
      sessionResponse({ defaults: DEFAULTS, defaultsRev: "r1" }),
    );
    const store = useAuthStore();
    await store.loadSession();
    expect(store.defaults).toEqual(DEFAULTS);
    expect(store.defaultsRev).toBe("r1");
  });

  it("loadAdminFlags keeps them too, and clears them when withheld", async () => {
    API.getSession.mockResolvedValueOnce(
      sessionResponse({ defaults: DEFAULTS, defaultsRev: "r1" }),
    );
    const store = useAuthStore();
    await store.loadAdminFlags();
    expect(store.defaults).toEqual(DEFAULTS);
    expect(store.defaultsRev).toBe("r1");

    // Non-Users turned off: the anonymous payload omits both.
    API.getSession.mockResolvedValueOnce(sessionResponse());
    await store.loadAdminFlags();
    expect(store.defaults).toBeUndefined();
    expect(store.defaultsRev).toBeUndefined();
  });
});

function stores(rev) {
  const auth = useAuthStore();
  auth.defaultsRev = rev;
  const browser = useBrowserStore();
  browser.loadSettings = vi.fn();
  const reader = useReaderStore();
  reader.loadGlobalSettings = vi.fn();
  return { auth, browser, reader };
}

describe("reloadOnDefaultsChange", () => {
  it("reloads the browser settings when defaultsRev changed", async () => {
    API.getSession.mockResolvedValue(sessionResponse({ defaultsRev: "r2" }));
    const { browser, reader } = stores("r1");
    expect(await reloadOnDefaultsChange("browser")).toBe(true);
    expect(browser.loadSettings).toHaveBeenCalledOnce();
    expect(reader.loadGlobalSettings).not.toHaveBeenCalled();
  });

  it("reloads the reader's global settings on the reader route", async () => {
    API.getSession.mockResolvedValue(sessionResponse({ defaultsRev: "r2" }));
    const { browser, reader } = stores("r1");
    await reloadOnDefaultsChange("reader");
    expect(reader.loadGlobalSettings).toHaveBeenCalledOnce();
    expect(browser.loadSettings).not.toHaveBeenCalled();
  });

  it("does nothing when defaultsRev is unchanged", async () => {
    API.getSession.mockResolvedValue(sessionResponse({ defaultsRev: "r1" }));
    const { browser } = stores("r1");
    expect(await reloadOnDefaultsChange("browser")).toBe(false);
    expect(browser.loadSettings).not.toHaveBeenCalled();
  });

  it("does nothing on the first load, from an undefined revision", async () => {
    API.getSession.mockResolvedValue(sessionResponse({ defaultsRev: "r1" }));
    const { browser } = stores();
    expect(await reloadOnDefaultsChange("browser")).toBe(false);
    expect(browser.loadSettings).not.toHaveBeenCalled();
  });
});

describe("useAuthStore — API keys", () => {
  const KOBO = Object.freeze({
    pk: 1,
    name: "Kobo",
    scope: "device",
    prefix: "abcd",
  });

  it("loads the key list", async () => {
    API.getApiKeys.mockResolvedValue({ data: { keys: [KOBO] } });
    const store = useAuthStore();
    await store.loadApiKeys();
    expect(store.apiKeys).toEqual([KOBO]);
  });

  it("returns the new key once and keeps it out of the list", async () => {
    API.createApiKey.mockResolvedValue({
      data: {
        pk: 2,
        name: "Grafana",
        scope: "stats",
        prefix: "wxyz",
        key: "wxyzsecret",
      },
    });
    const store = useAuthStore();
    store.apiKeys = [{ ...KOBO }];
    const key = await store.createApiKey({ name: "Grafana", scope: "stats" });
    expect(key).toBe("wxyzsecret");
    expect(API.createApiKey).toHaveBeenCalledWith({
      name: "Grafana",
      scope: "stats",
    });
    expect(store.apiKeys.map((row) => row.name)).toEqual(["Grafana", "Kobo"]);
    expect(JSON.stringify(store.apiKeys)).not.toContain("wxyzsecret");
  });

  it("rejects a refused create and leaves the shared form errors alone", async () => {
    /*
     * What the interceptor really hands over: the view's
     * ``{"detail": "<sentence>"}`` arrives as the envelope error's detail
     * string. The API Access dialog shows it itself: the shared form errors
     * are what the Profile dialog underneath renders.
     */
    const refusal = new APIError(
      {
        status: "400",
        title: "Bad Request",
        detail: "You already have a key named Kobo.",
      },
      400,
    );
    API.createApiKey.mockRejectedValue(refusal);
    const store = useAuthStore();
    await expect(
      store.createApiKey({ name: "Kobo", scope: "device" }),
    ).rejects.toBe(refusal);
    expect(useCommonStore().form.errors).toStrictEqual([]);
  });

  it("says so when the key list fails to load", async () => {
    API.getApiKeys.mockRejectedValueOnce(new Error("down"));
    const store = useAuthStore();
    await store.loadApiKeys();
    expect(store.apiKeysError).toBe("Could not load your API keys.");
    API.getApiKeys.mockResolvedValueOnce({ data: { keys: [KOBO] } });
    await store.loadApiKeys();
    expect(store.apiKeysError).toBe("");
    expect(store.apiKeys).toEqual([KOBO]);
  });

  it("drops a revoked key", async () => {
    API.deleteApiKey.mockResolvedValue({});
    const store = useAuthStore();
    store.apiKeys = [{ ...KOBO }];
    expect(await store.deleteApiKey(1)).toBe(true);
    expect(API.deleteApiKey).toHaveBeenCalledWith(1);
    expect(store.apiKeys).toEqual([]);
  });

  it("clears keys and URLs on logout", async () => {
    API.logout.mockResolvedValue({});
    API.getSession.mockResolvedValue(sessionResponse());
    const store = useAuthStore();
    store.user = { username: "alice" };
    store.apiKeys = [{ ...KOBO }];
    store.apiUrls = Object.freeze({ opdsV1: "/opds/v1.2/" });
    await store.logout();
    expect(store.apiKeys).toEqual([]);
    expect(store.apiUrls).toBeUndefined();
  });
});

describe("useAuthStore — API URLs", () => {
  it("reloads on every call, never from a cache", async () => {
    API.getApiUrls.mockResolvedValueOnce({ data: { opdsV1: "/opds/v1.2/" } });
    API.getApiUrls.mockResolvedValueOnce({ data: {} });
    const store = useAuthStore();
    await store.loadApiUrls();
    expect(store.apiUrls).toEqual({ opdsV1: "/opds/v1.2/" });
    await store.loadApiUrls();
    expect(API.getApiUrls).toHaveBeenCalledTimes(2);
    expect(store.apiUrls).toEqual({});
  });

  it("reports a failure instead of spinning", async () => {
    API.getApiUrls.mockRejectedValue(new Error("down"));
    const store = useAuthStore();
    await store.loadApiUrls();
    expect(store.apiUrls).toBeUndefined();
    expect(store.apiUrlsError).toBe("Could not load the API URLs.");
  });
});
