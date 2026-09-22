/*
 * The OPDS dialog must always render something.
 *
 * Reported as "the window goes inactive but no new window appears"
 * (#855). Two ways that happened: a failed request left `opdsURLs`
 * undefined forever with no error state, and the loading placeholder is
 * percentage-sized, which resolves to nothing inside the shrink-to-fit
 * overlay box unless the body has an intrinsic size.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import OPDSDialog from "@/components/settings/opds-dialog.vue";
import vuetify from "@/plugins/vuetify";

// v-dialog teleports and only renders when activated; stub it so the
// body is in the tree.
const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };

function mountDialog(common = {}) {
  const pinia = createTestingPinia({
    initialState: {
      common: { opdsURLs: undefined, opdsURLsError: "", ...common },
    },
  });
  return mount(OPDSDialog, {
    global: {
      plugins: [vuetify, pinia],
      stubs: { VDialog: VDialogStub },
    },
  });
}

describe("OPDSDialog", () => {
  test("renders the urls once they load", () => {
    const wrapper = mountDialog({
      opdsURLs: { v1: "/opds/v1.2/", v2: "/opds/v2.0/" },
    });

    expect(wrapper.find("#opds").exists()).toBe(true);
    expect(wrapper.find("#opdsError").exists()).toBe(false);
    expect(wrapper.find("#opdsLoading").exists()).toBe(false);
  });

  test("shows an error with a retry when the request fails", () => {
    const wrapper = mountDialog({
      opdsURLsError: "Could not load the OPDS urls.",
    });

    const error = wrapper.find("#opdsError");
    expect(error.exists()).toBe(true);
    expect(error.text()).toContain("Could not load");
    expect(error.text()).toContain("Retry");
    expect(wrapper.find("#opdsLoading").exists()).toBe(false);
  });

  test("shows a sized placeholder while loading", () => {
    const wrapper = mountDialog();

    expect(wrapper.find("#opdsLoading").exists()).toBe(true);
    // An explicit size is what keeps the percentage rule from
    // collapsing the overlay to a sliver.
    const progress = wrapper.find(".v-progress-circular");
    expect(progress.exists()).toBe(true);
    expect(progress.attributes("style")).toContain("64px");
  });

  test("the body is wrapped so the overlay has an intrinsic size", () => {
    const wrapper = mountDialog();

    expect(wrapper.find(".v-card").exists()).toBe(true);
  });
});
