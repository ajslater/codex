/*
 * Unit tests for the admin store's OIDC settings actions:
 * loadOidcSettings (TTL-gated), updateOidcSettings, testOidcConnection.
 * HTTP layer mocked; admin gate driven through the auth store.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock(import("@/api/v4/admin"), async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    getOidcSettings: vi.fn(),
    updateOidcSettings: vi.fn(),
    testOidcConnection: vi.fn(),
  };
});

import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";

import * as API from "@/api/v4/admin";
import AuthTab, { canEnableOidc } from "@/components/admin/tabs/auth-tab.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

const SETTINGS = Object.freeze({
  enabled: true,
  providerName: "Authentik",
  serverUrl: "https://idp.example.com",
  clientId: "codex",
  clientSecretSet: true,
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

describe("canEnableOidc — enable-switch gate", () => {
  const complete = Object.freeze({
    providerName: "Authentik",
    serverUrl: "https://idp.example.com",
    clientId: "codex",
  });

  it("requires a provider name, a valid server URL, and a client ID", () => {
    expect(canEnableOidc({})).toBe(false);
    expect(canEnableOidc({ ...complete, providerName: "" })).toBe(false);
    expect(canEnableOidc({ ...complete, serverUrl: "" })).toBe(false);
    expect(canEnableOidc({ ...complete, clientId: "" })).toBe(false);
    expect(canEnableOidc({ ...complete, serverUrl: "not a url" })).toBe(false);
    expect(canEnableOidc(complete)).toBe(true);
  });
});

function mountTab(oidcSettings) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { id: 1, username: "admin", isStaff: true } },
      admin: { oidcSettings, flags: [] },
    },
  });
  return mount(AuthTab, { global: { plugins: [vuetify, pinia] } });
}

describe("AuthTab — OIDC disclosure", () => {
  it("starts collapsed when OIDC is disabled", () => {
    const wrapper = mountTab({ ...SETTINGS, enabled: false });
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.find(".adminExpandToggle").text()).toContain("Configure");
    expect(wrapper.text()).toContain("Not enabled");
  });

  it("starts expanded when OIDC is enabled", () => {
    const wrapper = mountTab(SETTINGS);
    expect(wrapper.find("form").exists()).toBe(true);
    expect(wrapper.find(".adminExpandToggle").text()).toContain("Hide");
  });

  it("expands on toggle click", async () => {
    const wrapper = mountTab({ ...SETTINGS, enabled: false });
    await wrapper.find(".adminExpandToggle").trigger("click");
    expect(wrapper.find("form").exists()).toBe(true);
  });
});

describe("useAdminStore — OIDC settings", () => {
  it("loads settings into state", async () => {
    API.getOidcSettings.mockResolvedValue({ data: SETTINGS });
    const store = adminStore();
    await store.loadOidcSettings();
    expect(store.oidcSettings).toEqual(SETTINGS);
  });

  it("respects the TTL and refetches with force", async () => {
    API.getOidcSettings.mockResolvedValue({ data: SETTINGS });
    const store = adminStore();
    await store.loadOidcSettings();
    await store.loadOidcSettings();
    expect(API.getOidcSettings).toHaveBeenCalledTimes(1);
    await store.loadOidcSettings({ force: true });
    expect(API.getOidcSettings).toHaveBeenCalledTimes(2);
  });

  it("denies non-admins", async () => {
    useAuthStore().user = { id: 2, username: "reader" };
    const store = useAdminStore();
    await store.loadOidcSettings();
    expect(API.getOidcSettings).not.toHaveBeenCalled();
  });

  it("update round-trips server state and refreshes auth public flags", async () => {
    API.updateOidcSettings.mockResolvedValue({
      data: { ...SETTINGS, providerName: "Renamed" },
    });
    const store = adminStore();
    // Saving OIDC settings must resync the auth store's public flags so the
    // login button reflects the change without a page reload.
    const refresh = vi
      .spyOn(useAuthStore(), "loadAdminFlags")
      .mockResolvedValue(true);
    await store.updateOidcSettings({ providerName: "Renamed" });
    expect(API.updateOidcSettings).toHaveBeenCalledWith({
      providerName: "Renamed",
    });
    expect(store.oidcSettings.providerName).toBe("Renamed");
    expect(refresh).toHaveBeenCalled();
  });

  it("test connection returns the endpoint report", async () => {
    const report = { ok: true, issuer: "https://idp.example.com" };
    API.testOidcConnection.mockResolvedValue({ data: report });
    const store = adminStore();
    const result = await store.testOidcConnection({
      serverUrl: "https://idp.example.com",
    });
    expect(result).toEqual(report);
  });

  it("test connection surfaces errors as undefined", async () => {
    API.testOidcConnection.mockRejectedValue(new Error("boom"));
    const store = adminStore();
    const result = await store.testOidcConnection({});
    expect(result).toBeUndefined();
  });
});
