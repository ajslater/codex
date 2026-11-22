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
        page: { mtime: 1 },
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
  test("keeps its place with nothing ticked, so a first tick moves no row", () => {
    const { wrapper } = mountSubmenu({
      dynamic: { characters: [{ pk: 1, name: "Spider-Man" }] },
    });
    const clear = wrapper.find(".clearFilter");
    expect(clear.exists()).toBe(true);
    expect(clear.classes()).toContain("clearFilterIdle");
    expect(clear.attributes("aria-hidden")).toBe("true");
  });

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

const METRON = Object.freeze([{ pk: 3, name: "Teen", index: 2 }]);
const TAGGED = Object.freeze([
  { pk: 9, name: "T", index: 2, metronName: "Teen" },
]);

describe("the filter list row", () => {
  test("a filter with ticks is drawn at full strength", async () => {
    const { wrapper, browserStore } = mountSubmenu({
      filters: { characters: [1] },
      dynamic: { characters: [{ pk: 1, name: "Spider-Man" }] },
    });
    browserStore.filterMode = "base";
    await flushPromises();
    const row = wrapper.find(".filterSubMenuRow");
    expect(row.classes()).toContain("filterRowTicked");
  });
});

describe("stale choices refresh in place", () => {
  test("a tick on one Age Rating tab refreshes the other after the page loads", async () => {
    const { wrapper, browserStore } = mountSubmenu({
      name: "ageRatingMetron",
      filters: { ageRatingMetron: [], ageRatingTagged: [] },
      dynamic: { ageRatingMetron: METRON, ageRatingTagged: TAGGED },
    });
    wrapper.vm.onAgeRatingSelected("ageRatingTagged", [9]);
    await flushPromises();
    expect(browserStore.loadFilterChoices).not.toHaveBeenCalled();
    browserStore.page = { mtime: 2 };
    await flushPromises();
    expect(browserStore.loadFilterChoices).toHaveBeenCalledExactlyOnceWith(
      "ageRatingMetron",
    );
    browserStore.page = { mtime: 3 };
    await flushPromises();
    expect(browserStore.loadFilterChoices).toHaveBeenCalledOnce();
  });

  test("a tick elsewhere refreshes nothing: its own list does not change", async () => {
    const { wrapper, browserStore } = mountSubmenu({
      filters: { characters: [] },
      dynamic: { characters: [{ pk: 1, name: "Spider-Man" }] },
    });
    wrapper.vm.onSelected([1]);
    browserStore.page = { mtime: 2 };
    await flushPromises();
    expect(browserStore.loadFilterChoices).not.toHaveBeenCalled();
  });

  test("lists emptied while the sub-menu is open load again", async () => {
    const { browserStore } = mountSubmenu({
      dynamic: { characters: [{ pk: 1, name: "Spider-Man" }] },
    });
    browserStore.choices.dynamic = { characters: true };
    await flushPromises();
    expect(browserStore.loadFilterChoices).toHaveBeenCalledWith("characters");
  });
});
