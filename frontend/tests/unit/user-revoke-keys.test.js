/*
 * Revoking all of a user's keys lives in Edit User, behind a confirmation.
 *
 * It used to be a one-click icon in the Users table that armed on the first
 * click and revoked on the second, which an admin triggered by accident.
 *
 * Behavior locked in here:
 *   - Edit User shows the key count and a "Revoke all keys" button that
 *     revokes only after Confirm, even at a (maybe stale) count of 0.
 *   - Add User shows neither.
 *   - The table reload that follows a revoke keeps the admin's unsaved
 *     edits, because the reloaded row changed no field the form edits.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import UserInputs from "@/components/admin/create-update-dialog/user-create-update-inputs.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";

const VDialogStub = Object.freeze({
  name: "VDialog",
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: `<div class="dialogStub">
    <slot name="activator" :props="{ onClick: () => $emit('update:modelValue', true) }" />
    <slot v-if="modelValue" />
  </div>`,
});

const USER = Object.freeze({
  pk: 7,
  username: "reader",
  email: "reader@example.com",
  isStaff: false,
  isActive: true,
  groups: [],
  ageRatingMetron: null,
  apiKeyCount: 3,
});

function mountInputs(oldRow) {
  const pinia = createTestingPinia({
    initialState: {
      common: { form: { errors: [], fieldErrors: {}, success: "" } },
      admin: { users: [], groups: [], ageRatingMetrons: [] },
    },
  });
  const wrapper = mount(UserInputs, {
    props: { oldRow },
    global: {
      plugins: [pinia, vuetify],
      stubs: { AdminRelationPicker: true, VDialog: VDialogStub },
    },
  });
  return { wrapper, store: useAdminStore() };
}

function revokeButton(wrapper) {
  return wrapper
    .findAll("button")
    .find((button) => button.text() === "Revoke all keys");
}

describe("Edit User revokes every key behind a confirmation", () => {
  test("shows the count, and revokes only after Confirm", async () => {
    const { wrapper, store } = mountInputs({ ...USER });
    expect(wrapper.text()).toContain("API Keys: 3");

    await revokeButton(wrapper).trigger("click");
    expect(store.revokeUserKeys).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("logged out");

    await wrapper.find(".confirmButton").trigger("click");
    expect(store.revokeUserKeys).toHaveBeenCalledExactlyOnceWith(7);
  });

  test("Cancel revokes nothing", async () => {
    const { wrapper, store } = mountInputs({ ...USER });
    await revokeButton(wrapper).trigger("click");
    await wrapper.find(".cancelButton").trigger("click");
    expect(store.revokeUserKeys).not.toHaveBeenCalled();
  });

  test("a count of 0 still offers the button", async () => {
    /*
     * The count is the Users table's, and a user making or revoking their
     * own keys never reloads it: 0 may be stale. Revoking nothing is
     * harmless; hiding the button left an admin unable to revoke.
     */
    const { wrapper, store } = mountInputs({ ...USER, apiKeyCount: 0 });
    expect(wrapper.text()).toContain("No API keys.");

    await revokeButton(wrapper).trigger("click");
    await wrapper.find(".confirmButton").trigger("click");
    expect(store.revokeUserKeys).toHaveBeenCalledExactlyOnceWith(7);
  });

  test("Add User shows neither", () => {
    const { wrapper } = mountInputs(false);
    expect(wrapper.text()).not.toContain("API Keys");
    expect(wrapper.text()).not.toContain("No API keys.");
  });
});

describe("a reloaded row keeps unsaved edits", () => {
  test("a new count from the server keeps the edited email", async () => {
    const { wrapper } = mountInputs({ ...USER });
    wrapper.vm.row.email = "edited@example.com";

    await wrapper.setProps({ oldRow: { ...USER, apiKeyCount: 0 } });

    expect(wrapper.vm.row.email).toBe("edited@example.com");
    expect(wrapper.vm.row.apiKeyCount).toBe(0);
    expect(wrapper.text()).toContain("No API keys.");
  });

  test("a server change to an edited field resets the form", async () => {
    const { wrapper } = mountInputs({ ...USER });
    wrapper.vm.row.email = "edited@example.com";

    await wrapper.setProps({
      oldRow: { ...USER, email: "changed@example.com" },
    });

    expect(wrapper.vm.row.email).toBe("changed@example.com");
  });
});
