/*
 * A reading list's missing issue in the grid: what it shows, and the menu
 * its editors get.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

vi.mock("@/api/v4/reading-lists", () => ({
  updateEntry: vi.fn(() => Promise.resolve({ data: {} })),
  getCandidates: vi.fn(() => Promise.resolve({ data: { candidates: [] } })),
}));

import * as API from "@/api/v4/reading-lists";
import MissingCard from "@/components/browser/missing/missing-card.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

const ENTRY = Object.freeze({
  pk: 7,
  position: 2,
  seriesName: "Civil War: Front Line",
  issue: "1",
  year: 2006,
  entryType: "tie-in",
});
const STUBS = Object.freeze({ VDialog: { template: "<div><slot /></div>" } });

function mountCard(editable) {
  const pinia = createTestingPinia({ createSpy: vi.fn, stubActions: true });
  const wrapper = mount(MissingCard, {
    props: { entry: ENTRY, readingListPk: 3, editable },
    global: { plugins: [pinia, vuetify], stubs: STUBS },
  });
  return { wrapper, browser: useBrowserStore() };
}

describe("MissingCard", () => {
  test("shows the issue and its place counting from 1", () => {
    const { wrapper } = mountCard(false);
    const text = wrapper.text();
    expect(text).toContain("Civil War: Front Line");
    expect(text).toContain("#1");
    expect(text).toContain("(2006)");
    expect(text).toContain("tie-in");
    expect(wrapper.find(".missingPlace").text()).toBe("3");
    expect(wrapper.attributes("title")).toBe(
      "Missing: Civil War: Front Line #1 (2006)",
    );
  });

  test("a viewer who may not edit the list gets no menu", () => {
    const { wrapper } = mountCard(false);
    expect(wrapper.find(".missingMenuButton").exists()).toBe(false);
  });

  test("Hide from List hides the entry and refreshes the page", async () => {
    const { wrapper, browser } = mountCard(true);
    expect(wrapper.find(".missingMenuButton").exists()).toBe(true);
    await wrapper.vm.hide();
    await flushPromises();
    expect(API.updateEntry).toHaveBeenCalledWith(3, 7, { ignored: true });
    expect(browser.refreshBrowserPage).toHaveBeenCalled();
  });
});
