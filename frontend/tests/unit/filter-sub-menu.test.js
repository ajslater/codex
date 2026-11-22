/*
 * One filter's sub-menu inside the filter menu: its header (back, Clear
 * Filter, search) and its checklist of choices.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, test } from "vitest";

import BrowserFilterSubMenu from "@/components/browser/toolbars/top/filter-sub-menu.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

const wrappers = [];

function mountSubmenu({
  name = "characters",
  filters = {},
  dynamic = {},
} = {}) {
  const pinia = createTestingPinia({
    initialState: {
      browser: {
        filterMode: name,
        filterMenuOpen: true,
        settings: { filters: { bookmark: "", ...filters } },
        choices: { dynamic },
      },
    },
  });
  const wrapper = mount(BrowserFilterSubMenu, {
    props: { name },
    global: { plugins: [pinia, vuetify] },
  });
  wrappers.push(wrapper);
  return { wrapper, browserStore: useBrowserStore() };
}

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
});

describe("Clear Filter", () => {
  test("returns to the filter list", async () => {
    const { wrapper, browserStore } = mountSubmenu({
      filters: { characters: [1] },
      dynamic: { characters: [{ pk: 1, name: "Spider-Man" }] },
    });
    await wrapper.find(".clearFilter").trigger("click");
    await flushPromises();
    expect(browserStore.clearOneFilter).toHaveBeenCalledWith("characters");
    expect(browserStore.filterMode).toBe("base");
  });

  test("on Age Rating, clears both tabs and returns to the list", async () => {
    const { wrapper, browserStore } = mountSubmenu({
      name: "ageRatingMetron",
      filters: { ageRatingMetron: [3], ageRatingTagged: [] },
      dynamic: { ageRatingMetron: [{ pk: 3, name: "Teen", index: 2 }] },
    });
    await wrapper.find(".clearFilter").trigger("click");
    await flushPromises();
    expect(browserStore.setSettings).toHaveBeenCalledWith({
      filters: { ageRatingMetron: [], ageRatingTagged: [] },
    });
    expect(browserStore.filterMode).toBe("base");
  });
});
