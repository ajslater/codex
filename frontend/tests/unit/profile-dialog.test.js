/*
 * Tests for the Profile dialog's client-side validation and Save gating.
 *
 * Behavior locked in here:
 *   - Fields validate client-side (email format, username required, password
 *     length, password-confirm match). The rules live on the component, so we
 *     exercise them directly.
 *   - The Save button is gated synchronously: it enables only on a valid,
 *     changed form. It must NOT depend on the auth-form-mixin's async
 *     `submitButtonEnabled` flag, and the dialog must not alias `credentials`
 *     (which would re-enable the mixin's per-keystroke whole-form validation).
 *   - An open-but-empty "Change Password" panel must not block a profile edit.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ProfileDialog from "@/components/auth/profile-dialog.vue";
import vuetify from "@/plugins/vuetify";

function mountDialog() {
  const pinia = createTestingPinia({
    initialState: {
      auth: {
        user: { username: "alice", email: "" },
        adminFlags: { emailEnabled: true, remoteUserEnabled: false },
        MIN_PASSWORD_LENGTH: 4,
      },
    },
  });
  return mount(ProfileDialog, {
    global: {
      plugins: [vuetify, pinia],
      stubs: {
        CodexListItem: true,
        AuthTokenDialog: true,
        SubmitFooter: true,
        CloseButton: true,
      },
    },
  });
}

describe("ProfileDialog Save gating", () => {
  test("enables only for a valid, changed email", async () => {
    const wrapper = mountDialog();
    const vm = wrapper.vm;

    // Initialize the form from the user (what opening the dialog does).
    vm.reset();
    await vm.$nextTick();
    expect(vm.canSubmit).toBe(false); // nothing changed yet

    // The dialog must NOT opt into the auth-form-mixin's live `credentials`
    // watcher, or the whole form would re-validate on every keystroke.
    expect(vm.credentials).toBeUndefined();

    // A valid email change enables Save — synchronously, not via the mixin's
    // async `submitButtonEnabled` flag (which stays false here).
    vm.profile.email = "alice@example.com";
    await vm.$nextTick();
    expect(vm.submitButtonEnabled).toBe(false);
    expect(vm.canSubmit).toBe(true);

    // An invalid email keeps Save disabled (gated on validity).
    vm.profile.email = "not-an-email";
    await vm.$nextTick();
    expect(vm.canSubmit).toBe(false);

    // Reverting the change disables Save again.
    vm.profile.email = "";
    await vm.$nextTick();
    expect(vm.canSubmit).toBe(false);
  });

  test("password section gates Save on length and match", async () => {
    const wrapper = mountDialog();
    const vm = wrapper.vm;

    vm.reset();
    vm.passwordPanel = "password";
    await vm.$nextTick();

    // Too short -> disabled.
    vm.profile.oldPassword = "old-secret";
    vm.profile.password = "no";
    vm.profile.passwordConfirm = "no";
    await vm.$nextTick();
    expect(vm.canSubmit).toBe(false);

    // Long enough but the confirm doesn't match -> still disabled.
    vm.profile.password = "new-secret";
    vm.profile.passwordConfirm = "mismatch";
    await vm.$nextTick();
    expect(vm.canSubmit).toBe(false);

    // Length ok and confirm matches -> enabled.
    vm.profile.passwordConfirm = "new-secret";
    await vm.$nextTick();
    expect(vm.canSubmit).toBe(true);
  });

  test("an empty Change Password panel does not block a profile edit", async () => {
    const wrapper = mountDialog();
    const vm = wrapper.vm;

    vm.reset();
    vm.profile.email = "alice@example.com";
    vm.passwordPanel = "password"; // panel open, password fields left empty
    await vm.$nextTick();

    expect(vm.canSubmit).toBe(true);
  });
});

describe("ProfileDialog client-side rules", () => {
  test("email accepts blank or valid, rejects malformed", () => {
    const rule = mountDialog().vm.rules.email[0];
    expect(rule("")).toBe(true); // optional
    expect(rule("alice@example.com")).toBe(true);
    expect(rule("not-an-email")).toBe("Enter a valid email address");
  });

  test("username is required, with no minimum length (Django enforces none)", () => {
    const rule = mountDialog().vm.rules.username[0];
    expect(rule("")).toBe("Username is required");
    expect(rule("x")).toBe(true);
  });

  test("password enforces length, difference from old, and confirm match", async () => {
    const wrapper = mountDialog();
    const vm = wrapper.vm;
    vm.passwordPanel = "password";
    vm.profile.oldPassword = "old-secret";
    await vm.$nextTick();

    const passwordRule = vm.passwordRules.password[0];
    expect(passwordRule("")).toBe("New password is required");
    expect(passwordRule("abc")).toBe("Password must be at least 4 characters");
    expect(passwordRule("old-secret")).toBe(
      "New password must differ from old password",
    );
    expect(passwordRule("new-secret")).toBe(true);

    vm.profile.password = "new-secret";
    await vm.$nextTick();
    const confirmRule = vm.passwordRules.passwordConfirm[0];
    expect(confirmRule("nope")).toBe("Passwords must match");
    expect(confirmRule("new-secret")).toBe(true);
  });
});

export default {};
