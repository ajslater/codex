/*
 * A reading list's card says "31 of 98" when the library lacks some of it.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

import BrowserCardSubtitle from "@/components/browser/card/subtitle.vue";
import vuetify from "@/plugins/vuetify";

function subtitle(item) {
  return mount(BrowserCardSubtitle, {
    props: { item: { collection: "arcs", name: "Civil War", ...item } },
    global: {
      plugins: [
        createTestingPinia({ createSpy: vi.fn, stubActions: false }),
        vuetify,
      ],
    },
  });
}

describe("list coverage on a card", () => {
  test("a list with gaps says how much is here", () => {
    const wrapper = subtitle({ listInLibrary: 31, listTotal: 98 });
    expect(wrapper.find(".listCoverage").text()).toBe("31 of 98");
  });

  test("a complete list says nothing", () => {
    const wrapper = subtitle({ listInLibrary: 4, listTotal: 4 });
    expect(wrapper.find(".listCoverage").exists()).toBe(false);
  });

  test("another card says nothing", () => {
    const wrapper = subtitle({ collection: "series" });
    expect(wrapper.find(".listCoverage").exists()).toBe(false);
  });
});
