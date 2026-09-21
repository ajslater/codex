/*
 * Tests for the change-password dialog's client-side validation.
 *
 *   - The minimum comes from the generated ``limits.json``, which the
 *     server derives from the same constant it enforces. The rule used
 *     to read a store key nothing mapped, so it compared against
 *     ``undefined`` and never fired -- a typo in the generated key
 *     reintroduces exactly that, which the guard below catches.
 *   - The wording matches the other four password rules in the app.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ChangePasswordDialog from "@/components/auth/change-password-dialog.vue";
import LIMITS from "@/choices/limits.json";
import vuetify from "@/plugins/vuetify";

const MIN = LIMITS.passwordMinLength;
const OLD_PASSWORD = "oldpassword";
const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };

function mountDialog() {
  const pinia = createTestingPinia({
    initialState: {
      auth: {
        showChangePasswordDialog: true,
      },
      common: { form: { errors: [], success: "" } },
    },
  });
  return mount(ChangePasswordDialog, {
    props: { user: { pk: 1, username: "alice" } },
    global: {
      plugins: [vuetify, pinia],
      stubs: {
        VDialog: VDialogStub,
        SubmitFooter: true,
        CodexListItem: true,
        CloseButton: true,
      },
    },
  });
}

async function validateWith(wrapper, password) {
  wrapper.vm.credentials.oldPassword = OLD_PASSWORD;
  wrapper.vm.credentials.password = password;
  wrapper.vm.credentials.passwordConfirm = password;
  await flushPromises();
  const { valid, errors } = await wrapper.vm.$refs.form.validate();
  return { valid, messages: errors.flatMap((e) => e.errorMessages) };
}

describe("ChangePasswordDialog password minimum", () => {
  test("the generated minimum is a real number", () => {
    // A misspelled key yields undefined, and ``v.length < undefined``
    // is always false -- which is how this rule silently never fired.
    expect(typeof MIN).toBe("number");
    expect(MIN).toBeGreaterThan(0);
  });

  test("rejects a password shorter than the store minimum", async () => {
    const { valid, messages } = await validateWith(
      mountDialog(),
      "a".repeat(MIN - 1),
    );
    expect(valid).toBe(false);
    expect(messages).toContain(`Password must be at least ${MIN} characters`);
  });

  test("accepts a password at the minimum", async () => {
    const { valid } = await validateWith(mountDialog(), "a".repeat(MIN));
    expect(valid).toBe(true);
  });

  test("rejects reusing the old password", async () => {
    const { valid, messages } = await validateWith(mountDialog(), OLD_PASSWORD);
    expect(valid).toBe(false);
    expect(messages).toContain(
      "New password must be different than old password",
    );
  });
});

export default {};
