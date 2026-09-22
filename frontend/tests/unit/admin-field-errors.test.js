/*
 * The server's reason lands on the field that caused it.
 *
 * The client used to scan its own loaded list for a duplicate name,
 * which is both a guess and wrong past the first page: ``loadTable``
 * reads only ``body.results`` and never follows ``next``, so with a page
 * size of 200 a duplicate on row 201 was never caught. The server has
 * always been authoritative -- ``username``, ``Group.name`` and
 * ``Library.path`` are all ``unique=True`` and ModelSerializer attaches
 * the UniqueValidator automatically -- so what was missing was somewhere
 * to put its answer.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import GroupInputs from "@/components/admin/create-update-dialog/group-create-update-inputs.vue";
import UserInputs from "@/components/admin/create-update-dialog/user-create-update-inputs.vue";
import vuetify from "@/plugins/vuetify";

const TAKEN_USER = "A user with that username already exists.";
const TAKEN_GROUP = "Group with this Name already exists.";

function mountInputs(component, fieldErrors, adminState = {}) {
  const pinia = createTestingPinia({
    initialState: {
      common: { form: { errors: [], fieldErrors, success: "" } },
      admin: {
        users: [],
        groups: [],
        libraries: [],
        ageRatingMetrons: [],
        ...adminState,
      },
    },
  });
  return mount(component, {
    props: { oldRow: undefined },
    global: {
      plugins: [pinia, vuetify],
      stubs: { AdminRelationPicker: true },
    },
  });
}

describe("admin dialogs show the server's field errors", () => {
  test("a duplicate username renders on the username field", () => {
    const wrapper = mountInputs(UserInputs, { username: [TAKEN_USER] });

    expect(wrapper.text()).toContain(TAKEN_USER);
  });

  test("an email error renders on the email field, not the username", () => {
    const wrapper = mountInputs(UserInputs, {
      email: ["Enter a valid email address."],
    });

    const fields = wrapper.findAllComponents({ name: "VTextField" });
    const username = fields.find((f) => f.props("label") === "Username");
    const email = fields.find((f) => f.props("label") === "Email");

    expect(email.props("errorMessages")).toStrictEqual([
      "Enter a valid email address.",
    ]);
    // Vuetify normalizes an absent binding to an empty array.
    expect(username.props("errorMessages")).toStrictEqual([]);
  });

  test("a duplicate group name renders on the name field", () => {
    const wrapper = mountInputs(GroupInputs, { name: [TAKEN_GROUP] });

    expect(wrapper.text()).toContain(TAKEN_GROUP);
  });

  test("no server error means no message", () => {
    const wrapper = mountInputs(UserInputs, {});

    expect(wrapper.text()).not.toContain(TAKEN_USER);
  });
});

export default {};
