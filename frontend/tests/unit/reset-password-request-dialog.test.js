/*
 * Tests for the "Forgot password?" request dialog.
 *
 * On a successful send the dialog closes — the green "Reset link sent" banner
 * on the login screen (commonStore.form.success) is the only confirmation, so
 * there is no separate in-dialog "if that account…" message.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ResetPasswordRequestDialog from "@/components/auth/reset-password-request-dialog.vue";
import vuetify from "@/plugins/vuetify";
import { useAuthStore } from "@/stores/auth";

// Render the dialog body inline instead of through v-dialog's overlay/teleport
// (which need browser APIs happy-dom lacks). The activator slot is dropped.
const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };

function mountDialog() {
  const pinia = createTestingPinia();
  const wrapper = mount(ResetPasswordRequestDialog, {
    global: {
      plugins: [vuetify, pinia],
      stubs: { VDialog: VDialogStub, SubmitFooter: true },
    },
  });
  const store = useAuthStore();
  store.showResetPasswordRequestDialog = true;
  return { wrapper, store };
}

describe("ResetPasswordRequestDialog", () => {
  test("closes the dialog on a successful send", async () => {
    const { wrapper, store } = mountDialog();
    store.sendResetPasswordLink.mockResolvedValue(true);
    await wrapper.vm.$nextTick(); // open-watcher clears the login field

    wrapper.vm.login = "alice@example.com";
    await wrapper.vm.$nextTick();
    await wrapper.vm.submit();

    expect(store.sendResetPasswordLink).toHaveBeenCalledWith(
      "alice@example.com",
    );
    expect(store.showResetPasswordRequestDialog).toBe(false);
  });

  test("keeps the dialog open when the send fails", async () => {
    const { wrapper, store } = mountDialog();
    store.sendResetPasswordLink.mockResolvedValue(false);
    await wrapper.vm.$nextTick();

    wrapper.vm.login = "alice@example.com";
    await wrapper.vm.$nextTick();
    await wrapper.vm.submit();

    expect(store.showResetPasswordRequestDialog).toBe(true);
  });

  test("does not send when the field is empty (validation fails)", async () => {
    const { wrapper, store } = mountDialog();
    await wrapper.vm.$nextTick();

    // login left empty -> the field's required rule fails in form.validate()
    await wrapper.vm.submit();

    expect(store.sendResetPasswordLink).not.toHaveBeenCalled();
    expect(store.showResetPasswordRequestDialog).toBe(true);
  });
});

export default {};
