/*
 * The Add/Edit dialog's submit button follows the newest edit.
 *
 *   - Every edit re-validates the form, and form.validate() is async, so an
 *     older validation can settle after a newer one. The button used to take
 *     whichever settled last: a check of the empty name ("Name is required")
 *     landing after the check of "dup" left "Add Group" disabled on a valid
 *     form.
 *   - The inputs emit each edit from a watcher, before they re-render, so the
 *     form validated the field's value from before the edit. A name entered
 *     in one input event was checked as blank.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { markRaw } from "vue";

import CreateUpdateDialog from "@/components/admin/create-update-dialog/create-update-dialog.vue";
import GroupCreateUpdateInputs from "@/components/admin/create-update-dialog/group-create-update-inputs.vue";
import vuetify from "@/plugins/vuetify";

const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };

const mountDialog = (stubs = {}) =>
  mount(CreateUpdateDialog, {
    props: { table: "Group", inputs: markRaw(GroupCreateUpdateInputs) },
    global: {
      plugins: [
        createTestingPinia({ initialState: { admin: { libraries: [] } } }),
        vuetify,
      ],
      stubs: { VDialog: VDialogStub, ...stubs },
    },
  });

const isAddDisabled = (wrapper) =>
  wrapper.find("button.confirmButton").attributes("disabled") !== undefined;

// A form whose validations settle only when the test says so.
const mountWithPendingValidations = () => {
  const validations = [];
  const VFormStub = {
    name: "VForm",
    template: "<form><slot /></form>",
    methods: {
      validate: () =>
        new Promise((resolve) => {
          validations.push(resolve);
        }),
    },
  };
  const wrapper = mountDialog({ VForm: VFormStub });
  const type = async (name) => {
    wrapper.findComponent(GroupCreateUpdateInputs).vm.row.name = name;
    await flushPromises();
  };
  const settle = async (index, valid) => {
    validations[index]({ valid });
    await flushPromises();
  };
  return { wrapper, validations, type, settle };
};

describe("the Add/Edit dialog submit button", () => {
  it("ignores an older validation that settles last", async () => {
    const { wrapper, validations, type, settle } =
      mountWithPendingValidations();

    await type("d");
    await type("");
    await type("dup");
    expect(validations).toHaveLength(3);

    await settle(2, true);
    expect(isAddDisabled(wrapper)).toBe(false);

    // The check of the empty name lands after the check of "dup".
    await settle(0, true);
    await settle(1, false);
    expect(isAddDisabled(wrapper)).toBe(false);
  });

  it("takes the newest validation when it settles last", async () => {
    const { wrapper, type, settle } = mountWithPendingValidations();

    await type("dup");
    await type("");
    await settle(0, true);
    await settle(1, false);

    expect(isAddDisabled(wrapper)).toBe(true);
  });

  it("validates the name as entered, not as it was before", async () => {
    const wrapper = mountDialog();
    await flushPromises();
    expect(isAddDisabled(wrapper)).toBe(true);

    await wrapper.find("input").setValue("dup");
    await flushPromises();

    expect(isAddDisabled(wrapper)).toBe(false);
  });
});
