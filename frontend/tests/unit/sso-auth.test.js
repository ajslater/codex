/*
 * Unit tests for the SSO (OIDC) auth-store actions and components.
 *
 * ``loginSSO`` and the RP-initiated-logout leg of ``logout`` perform
 * full-page navigations via ``globalThis.location.assign`` — spied here,
 * never executed. The SSO button and error page render against real
 * Vuetify with a testing pinia.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/v4/auth", () => ({
  getSession: vi.fn(),
  register: vi.fn(),
  login: vi.fn(),
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
  logout: vi.fn(),
  updatePassword: vi.fn(),
  sendResetPasswordLink: vi.fn(),
  resetPassword: vi.fn(),
  updateTimezone: vi.fn(),
  getToken: vi.fn(),
  updateToken: vi.fn(),
}));

import * as API from "@/api/v4/auth";
import SsoError from "@/components/auth/sso-error.vue";
import SsoLoginButton from "@/components/auth/sso-login-button.vue";
import vuetify from "@/plugins/vuetify";
import { useAuthStore } from "@/stores/auth";

const LOGIN_URL = "/codex/api/v4/auth/oidc/login";

describe("useAuthStore — SSO actions", () => {
  let assign;

  beforeEach(() => {
    setActivePinia(createPinia());
    // spyOn returns the same spy on re-entry; clear its call history.
    assign = vi.spyOn(location, "assign").mockImplementation(() => {});
    assign.mockClear();
    for (const fn of Object.values(API)) {
      if (typeof fn?.mockReset === "function") {
        fn.mockReset();
      }
    }
  });

  it("loginSSO navigates to the prefix-qualified login URL", () => {
    const store = useAuthStore();
    store.adminFlags.oidcLoginUrl = LOGIN_URL;
    store.loginSSO();
    expect(assign).toHaveBeenCalledWith(LOGIN_URL);
  });

  it("loginSSO is a no-op when OIDC is not configured", () => {
    const store = useAuthStore();
    store.loginSSO();
    expect(assign).not.toHaveBeenCalled();
  });

  it("logout navigates to the RP-initiated logout URL when present", async () => {
    API.logout.mockResolvedValue({});
    const store = useAuthStore();
    store.adminFlags.oidcLogoutUrl =
      "https://idp.example.com/end-session/?client_id=codex";
    await store.logout();
    expect(store.user).toBeUndefined();
    expect(assign).toHaveBeenCalledWith(
      "https://idp.example.com/end-session/?client_id=codex",
    );
  });

  it("logout stays local and refreshes public flags without an oidcLogoutUrl", async () => {
    API.logout.mockResolvedValue({});
    // The logged-out /session reflects OIDC now disabled.
    API.getSession.mockResolvedValue({
      data: { adminFlags: { oidcEnabled: false } },
    });
    const store = useAuthStore();
    store.adminFlags.oidcEnabled = true; // stale from the just-ended session
    await store.logout();
    expect(assign).not.toHaveBeenCalled();
    expect(API.getSession).toHaveBeenCalled();
    expect(store.adminFlags.oidcEnabled).toBe(false);
  });

  it("logout skips the flag refresh when doing an RP-initiated redirect", async () => {
    API.logout.mockResolvedValue({});
    const store = useAuthStore();
    store.adminFlags.oidcLogoutUrl = "https://idp.example.com/end-session/";
    await store.logout();
    expect(API.getSession).not.toHaveBeenCalled();
  });
});

function mountWithFlags(component, adminFlags, mocks = {}) {
  const pinia = createTestingPinia({
    initialState: { auth: { adminFlags } },
  });
  return mount(component, {
    global: {
      plugins: [vuetify, pinia],
      mocks,
    },
  });
}

describe("SsoLoginButton", () => {
  it("renders the provider name when OIDC is enabled", () => {
    const wrapper = mountWithFlags(SsoLoginButton, {
      oidcEnabled: true,
      oidcProviderName: "Authentik",
    });
    const button = wrapper.find("#ssoLoginButton");
    expect(button.exists()).toBe(true);
    expect(button.text()).toContain("Login with Authentik");
  });

  it("renders nothing when OIDC is disabled", () => {
    const wrapper = mountWithFlags(SsoLoginButton, { oidcEnabled: false });
    expect(wrapper.find("#ssoLoginButton").exists()).toBe(false);
  });
});

function mountError(error) {
  return mountWithFlags(
    SsoError,
    { oidcEnabled: true, oidcProviderName: "SSO" },
    {
      $route: { query: error ? { error } : {} },
      $router: { push: vi.fn() },
    },
  );
}

describe("SsoError", () => {
  it("maps access_denied to a human message and offers retry", () => {
    const wrapper = mountError("access_denied");
    expect(wrapper.text()).toContain("denied the login request");
    expect(wrapper.find("#ssoLoginButton").exists()).toBe(true);
  });

  it("hides retry for signup_disabled", () => {
    const wrapper = mountError("signup_disabled");
    expect(wrapper.text()).toContain("Automatic account creation is disabled");
    expect(wrapper.find("#ssoLoginButton").exists()).toBe(false);
  });

  it("collapses unknown errors to the server_error message", () => {
    const wrapper = mountError("bogus_code");
    expect(wrapper.text()).toContain("could not be reached");
  });

  it("defaults to server_error with no query param", () => {
    const wrapper = mountError();
    expect(wrapper.text()).toContain("could not be reached");
  });
});
