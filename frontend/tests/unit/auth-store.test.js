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
  updateTimezone: vi.fn(),
  register: vi.fn(),
  login: vi.fn(),
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
  logout: vi.fn(),
  updatePassword: vi.fn(),
  sendResetPasswordLink: vi.fn(),
  resetPassword: vi.fn(),
  getToken: vi.fn(),
  updateToken: vi.fn(),
}));

import * as API from "@/api/v4/auth";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

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
  it("posts the login string and flips resetPasswordRequestSent", async () => {
    API.sendResetPasswordLink.mockResolvedValue({
      data: { detail: "Reset link sent" },
    });
    const store = useAuthStore();
    expect(store.resetPasswordRequestSent).toBe(false);
    const ok = await store.sendResetPasswordLink("alice");
    expect(ok).toBe(true);
    expect(API.sendResetPasswordLink).toHaveBeenCalledWith("alice");
    expect(store.resetPasswordRequestSent).toBe(true);
  });

  it("returns false and does not flip the sent flag on error", async () => {
    API.sendResetPasswordLink.mockRejectedValue(new Error("boom"));
    const store = useAuthStore();
    const ok = await store.sendResetPasswordLink("alice");
    expect(ok).toBe(false);
    expect(store.resetPasswordRequestSent).toBe(false);
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
