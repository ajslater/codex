/*
 * Tests for ``breadcrumbs.vue`` — the browser's crumb trail.
 *
 * The trail is built from the stored breadcrumbs, minus the last one,
 * which is where the reader already is and so is not a link. That
 * subtraction is what makes the empty case worth guarding: a group whose
 * parents have gone missing produces a single crumb, which becomes none
 * at all, stranding a deep view with no way out.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import Breadcrumbs from "@/components/browser/toolbars/breadcrumbs/breadcrumbs.vue";
import vuetify from "@/plugins/vuetify";

function mountCrumbs({ breadcrumbs, parentIds, topCollection = "publishers" }) {
  const pinia = createTestingPinia({
    initialState: {
      browser: {
        settings: { breadcrumbs, topCollection },
        collectionNames: {
          publishers: "Publishers",
          series: "Series",
          folders: "Folders",
        },
      },
      common: { timestamp: 1 },
    },
  });
  return mount(Breadcrumbs, {
    global: {
      plugins: [pinia, vuetify],
      mocks: { $route: { params: parentIds ? { parentIds } : {} } },
      stubs: {
        "v-breadcrumbs": true,
        "v-breadcrumbs-item": true,
        "v-icon": true,
      },
    },
  });
}

describe("BrowserBreadcrumbs", () => {
  it("links every crumb above the current one", () => {
    const wrapper = mountCrumbs({
      breadcrumbs: [
        { collection: "publishers", parentIds: [], name: "" },
        { collection: "series", parentIds: [5], name: "Captain Science" },
        { collection: "volumes", parentIds: [9], name: "1950" },
      ],
      parentIds: "9",
    });

    const crumbs = wrapper.vm.breadcrumbs;
    expect(crumbs).toHaveLength(2);
    expect(crumbs[1].text).toBe("Captain Science");
  });

  it("offers the top when a deep view has nothing to climb", () => {
    // One stored crumb becomes zero once the current one is dropped.
    const wrapper = mountCrumbs({
      breadcrumbs: [{ collection: "publishers", parentIds: [], name: "" }],
      parentIds: "9",
    });

    const crumbs = wrapper.vm.breadcrumbs;
    expect(crumbs).toHaveLength(1);
    expect(crumbs[0].tooltip.text).toBe("Top");
    expect(crumbs[0].to.params).toStrictEqual({ collection: "publishers" });
  });

  it("sends the reader to their own top collection", () => {
    const wrapper = mountCrumbs({
      breadcrumbs: [],
      parentIds: "9",
      topCollection: "folders",
    });

    expect(wrapper.vm.breadcrumbs[0].to.params).toStrictEqual({
      collection: "folders",
    });
  });

  it("offers nothing extra at the top itself", () => {
    // No parents in the route means we are already there.
    const wrapper = mountCrumbs({ breadcrumbs: [], parentIds: undefined });

    expect(wrapper.vm.breadcrumbs).toHaveLength(0);
  });

  it("survives breadcrumbs it was never given", () => {
    const wrapper = mountCrumbs({ breadcrumbs: undefined, parentIds: "9" });

    expect(wrapper.vm.breadcrumbs).toHaveLength(1);
    expect(wrapper.vm.breadcrumbs[0].tooltip.text).toBe("Top");
  });
});
