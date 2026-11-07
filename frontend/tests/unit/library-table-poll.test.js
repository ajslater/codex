/*
 * The library table's Poll split button.
 *
 * Behavior locked in here:
 *   - Each row's Poll control is a real VSplitBtn.
 *   - Its main button opens the Poll confirmation; confirming polls.
 *   - Its menu's one item opens the Force Update confirmation; confirming
 *     force-polls. Both confirmations live outside the menu, controlled by
 *     the table, so the menu closing can't unmount them.
 *   - Closing a confirmation without confirming runs nothing.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import LibraryTable from "@/components/admin/tabs/library-table.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";

const LIBRARY = Object.freeze({
  pk: 3,
  path: "/comics",
  comicCount: 10,
  events: true,
  poll: true,
  readOnly: false,
  pollEvery: "01:00:00",
  lastPoll: null,
  groups: [],
});

// Render the menu's content inline instead of through an overlay.
const VMenuStub = {
  name: "VMenu",
  template: '<div><slot name="activator" :props="{}" /><slot /></div>',
};

// A dialog that shows its content only while open, with no overlay.
const VDialogStub = {
  name: "VDialog",
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: '<div class="dialogStub"><slot v-if="modelValue" /></div>',
};

function confirmDialog(wrapper, titleText) {
  return wrapper
    .findAllComponents(ConfirmDialog)
    .find((dialog) => dialog.props("titleText") === titleText);
}

function mountTable() {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { isStaff: true } },
      admin: { groups: [], failedImports: [], pendingDeletes: [] },
      browser: { settings: { twentyFourHourTime: false } },
    },
  });
  const wrapper = mount(LibraryTable, {
    attrs: { items: [LIBRARY] },
    global: {
      plugins: [vuetify, pinia],
      stubs: {
        VMenu: VMenuStub,
        VDialog: VDialogStub,
        AdminCreateUpdateDialog: true,
        AdminDeleteRowDialog: true,
      },
    },
  });
  return { wrapper, store: useAdminStore() };
}

describe("LibraryTable — Poll split button", () => {
  test("the row's poll control is a split button", () => {
    const { wrapper } = mountTable();
    const split = wrapper.findComponent({ name: "VSplitBtn" });
    expect(split.exists()).toBe(true);
    expect(split.attributes("title")).toBe("Poll for updated comics");
  });

  test("the main button confirms, then polls", async () => {
    const { wrapper, store } = mountTable();
    const poll = () => confirmDialog(wrapper, "Poll for updated comics");
    expect(poll().props("modelValue")).toBe(false);

    await wrapper.find(".v-split-btn__action").trigger("click");
    expect(poll().props("modelValue")).toBe(true);

    await poll().find(".confirmButton").trigger("click");
    expect(store.librarianTask).toHaveBeenCalledWith(
      "poll",
      "Poll Library 3",
      3,
    );
    expect(poll().props("modelValue")).toBe(false);
  });

  test("the menu item confirms, then force-polls", async () => {
    const { wrapper, store } = mountTable();
    const force = () => confirmDialog(wrapper, "Force update comics");

    await wrapper.find(".v-split-btn .v-list-item").trigger("click");
    expect(force().props("modelValue")).toBe(true);

    await force().find(".confirmButton").trigger("click");
    expect(store.librarianTask).toHaveBeenCalledWith(
      "poll_force",
      "Force Poll Library 3",
      3,
    );
  });

  test("cancelling runs nothing and closes the dialog", async () => {
    const { wrapper, store } = mountTable();
    const poll = () => confirmDialog(wrapper, "Poll for updated comics");
    await wrapper.find(".v-split-btn__action").trigger("click");

    await poll().find(".cancelButton").trigger("click");
    expect(store.librarianTask).not.toHaveBeenCalled();
    expect(poll().props("modelValue")).toBe(false);
  });
});

export default {};
