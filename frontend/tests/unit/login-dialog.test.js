/*
 * Tests for the login/register dialog's client-side validation.
 *
 *   - The password minimum applies in register mode only; login accepts any
 *     non-empty password (the server decides).
 *   - The minimum comes from the auth store — the store is seeded with a
 *     value that differs from its default, so a misspelled store key or a
 *     hardcoded 4 can never silently pass again.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import AuthLoginDialog from "@/components/auth/login-dialog.vue";
import vuetify from "@/plugins/vuetify";

const MIN = 6; // deliberately not the store default of 4
const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };

function mountDialog() {
  const pinia = createTestingPinia({
    initialState: {
      auth: {
        MIN_PASSWORD_LENGTH: MIN,
        showLoginDialog: true,
        adminFlags: {
          registration: true,
          registerVerification: false,
          oidcEnabled: false,
        },
      },
    },
  });
  return mount(AuthLoginDialog, {
    global: {
      plugins: [vuetify, pinia],
      stubs: {
        VDialog: VDialogStub,
        SubmitFooter: true,
        CodexListItem: true,
        SsoLoginButton: true,
        ResetPasswordRequestDialog: true,
      },
    },
  });
}

async function validateWith(wrapper, { registerMode, password }) {
  wrapper.vm.registerMode = registerMode;
  await wrapper.vm.$nextTick();
  wrapper.vm.credentials.username = "alice";
  wrapper.vm.credentials.password = password;
  wrapper.vm.credentials.passwordConfirm = password;
  await flushPromises();
  const { valid, errors } = await wrapper.vm.$refs.form.validate();
  return { valid, messages: errors.flatMap((e) => e.errorMessages) };
}

describe("AuthLoginDialog password minimum", () => {
  test("register mode rejects a password shorter than the store minimum", async () => {
    const { valid, messages } = await validateWith(mountDialog(), {
      registerMode: true,
      password: "a".repeat(MIN - 1),
    });
    expect(valid).toBe(false);
    expect(messages).toContain(`Password must be at least ${MIN} characters`);
  });

  test("register mode accepts a password at the minimum", async () => {
    const { valid } = await validateWith(mountDialog(), {
      registerMode: true,
      password: "a".repeat(MIN),
    });
    expect(valid).toBe(true);
  });

  test("login mode does not enforce the minimum", async () => {
    const { valid } = await validateWith(mountDialog(), {
      registerMode: false,
      password: "a".repeat(MIN - 1),
    });
    expect(valid).toBe(true);
  });
});

export default {};
