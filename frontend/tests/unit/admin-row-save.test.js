/*
 * An admin Add/Edit dialog stays open when the server rejects the save.
 *
 * createRow and updateRow catch the rejection and hand it to the common
 * store, so they used to resolve either way and the dialog closed on every
 * settle. The server's field errors (a duplicate username, a taken group
 * name) landed in the store behind a closed dialog and were never seen.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";

import { TABLES } from "@/api/v4/admin";
import CreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const TAKEN = "Group with this Name already exists.";

// A plain xior error, as the JSON:API renderer produces it.
const takenNameError = () => ({
  response: { status: 400, data: { errors: { name: [TAKEN] } } },
});

const adminStore = () => {
  useAuthStore().user = { id: 1, username: "admin", isStaff: true };
  return useAdminStore();
};

const GroupInputs = defineComponent({
  name: "TestGroupInputs",
  EMPTY_ROW: Object.freeze({ name: "" }),
  UPDATE_KEYS: Object.freeze(["name"]),
  render: () => h("div"),
});

const mountDialog = (oldRow) =>
  mount(CreateUpdateDialog, {
    props: { table: "Group", inputs: GroupInputs, oldRow },
    // Stub VDialog: its overlay reads visualViewport, which the test DOM
    // lacks; these tests check the dialog's state, not the overlay.
    global: {
      plugins: [createTestingPinia(), vuetify],
      stubs: { VDialog: true },
    },
  });

describe("createRow and updateRow report whether the row saved", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it.each([
    ["createRow", "create", ["Group", { name: "g" }]],
    ["updateRow", "update", ["Group", 3, { name: "g" }]],
  ])(
    "%s resolves true and clears old errors when the row saves",
    async (action, method, args) => {
      vi.spyOn(TABLES.Group, method).mockResolvedValue({ data: {} });
      const store = adminStore();
      const loadTable = vi.spyOn(store, "loadTable").mockResolvedValue(true);
      useCommonStore().setErrors(takenNameError());

      await expect(store[action](...args)).resolves.toBe(true);

      expect(useCommonStore().form.fieldErrors).toStrictEqual({});
      expect(loadTable).toHaveBeenCalledWith("Group", { force: true });
    },
  );

  it.each([
    ["createRow", "create", ["Group", { name: "g" }]],
    ["updateRow", "update", ["Group", 3, { name: "g" }]],
  ])(
    "%s resolves false and keeps the field error when the server rejects it",
    async (action, method, args) => {
      vi.spyOn(TABLES.Group, method).mockRejectedValue(takenNameError());
      const store = adminStore();

      await expect(store[action](...args)).resolves.toBe(false);

      expect(useCommonStore().form.fieldErrors).toStrictEqual({
        name: [TAKEN],
      });
    },
  );
});

describe("the Add/Edit dialog", () => {
  it.each([
    ["Add", false, "createRow"],
    ["Edit", { pk: 3, name: "old" }, "updateRow"],
  ])(
    "%s stays open when the save fails and closes when it saves",
    async (_label, oldRow, action) => {
      const wrapper = mountDialog(oldRow);
      const store = useAdminStore();
      wrapper.vm.showDialog = true;
      wrapper.vm.row = { name: "new" };

      store[action].mockResolvedValue(false);
      await (oldRow ? wrapper.vm.doUpdate() : wrapper.vm.doCreate());
      expect(wrapper.vm.showDialog).toBe(true);

      store[action].mockResolvedValue(true);
      await (oldRow ? wrapper.vm.doUpdate() : wrapper.vm.doCreate());
      expect(wrapper.vm.showDialog).toBe(false);
    },
  );

  it("drops errors from an earlier attempt when it opens", async () => {
    const wrapper = mountDialog();
    const common = useCommonStore();

    wrapper.vm.showDialog = true;
    await flushPromises();

    expect(common.clearErrors).toHaveBeenCalledOnce();
  });
});
