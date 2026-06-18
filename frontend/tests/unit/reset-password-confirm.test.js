/*
 * Tests for the password-reset confirm screen.
 *
 *   - It reads the signed params from the (snake_case) query string.
 *   - On a successful reset it sends the user home with the login dialog open
 *     so they can sign in with the new password.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, test, vi } from "vitest";
import { createRouter, createWebHistory } from "vue-router";

import ResetPasswordConfirm from "@/components/auth/reset-password-confirm.vue";
import vuetify from "@/plugins/vuetify";
import { useAuthStore } from "@/stores/auth";

const Stub = { template: "<div />" };

function setupRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { name: "home", path: "/", component: Stub },
      {
        name: "reset-password",
        path: "/auth/reset-password",
        component: ResetPasswordConfirm,
      },
    ],
  });
}

async function mountConfirm(query) {
  const router = setupRouter();
  router.push({ name: "reset-password", query });
  await router.isReady();
  const pinia = createTestingPinia({
    initialState: {
      auth: { MIN_PASSWORD_LENGTH: 4, showLoginDialog: false },
    },
  });
  const wrapper = mount(ResetPasswordConfirm, {
    global: { plugins: [router, vuetify, pinia] },
  });
  return { wrapper, router, store: useAuthStore() };
}

describe("ResetPasswordConfirm", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  test("warns when the link is missing signed params", async () => {
    const { wrapper } = await mountConfirm({ user_id: "1" }); // no timestamp/signature
    expect(wrapper.vm.signaturePresent).toBe(false);
    expect(wrapper.text()).toContain("missing required parameters");
  });

  test("displays the username carried by the link", async () => {
    const { wrapper } = await mountConfirm({
      user_id: "1",
      timestamp: "123",
      signature: "abc",
      username: "alice",
    });
    expect(wrapper.vm.username).toBe("alice");
    expect(wrapper.text()).toContain("alice");
  });

  test("opens the login dialog after a successful reset", async () => {
    const { wrapper, router, store } = await mountConfirm({
      user_id: "1",
      timestamp: "123",
      signature: "abc",
    });
    store.resetPassword.mockResolvedValue(true);

    wrapper.vm.password = "longenough";
    wrapper.vm.passwordConfirm = "longenough";
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.canSubmit).toBe(true);

    vi.useFakeTimers();
    await wrapper.vm.submit();

    // Sends camelCase params (the JSON parser snake_case-ifies them) with the
    // timestamp coerced to a number.
    expect(store.resetPassword).toHaveBeenCalledWith({
      userId: "1",
      timestamp: 123,
      signature: "abc",
      password: "longenough",
    });

    // The login dialog opens only after the brief success-banner delay.
    expect(store.showLoginDialog).toBe(false);
    await vi.advanceTimersByTimeAsync(2000);
    expect(store.showLoginDialog).toBe(true);

    await flushPromises();
    expect(router.currentRoute.value.name).toBe("home");
  });

  test("does not open the login dialog when the reset fails", async () => {
    const { wrapper, store } = await mountConfirm({
      user_id: "1",
      timestamp: "123",
      signature: "abc",
    });
    store.resetPassword.mockResolvedValue(false);

    wrapper.vm.password = "longenough";
    wrapper.vm.passwordConfirm = "longenough";
    await wrapper.vm.$nextTick();

    vi.useFakeTimers();
    await wrapper.vm.submit();
    await vi.advanceTimersByTimeAsync(2000);

    expect(store.showLoginDialog).toBe(false);
  });
});

export default {};
