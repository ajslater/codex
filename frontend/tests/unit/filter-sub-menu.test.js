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

describe("the Match all ticked switch", () => {
  const SPIDEY = Object.freeze([{ pk: 1, name: "Spider-Man" }]);

  test("shows on tag-like filters only, ticked or not", () => {
    for (const [name, shown] of [
      ["characters", true],
      ["readingLists", true],
      ["seriesGroups", true],
      ["year", false],
      ["readingListKind", false],
      ["ageRatingMetron", false],
    ]) {
      const { wrapper } = mountSubmenu({ name, dynamic: { [name]: [] } });
      expect({ name, shown: wrapper.find(".matchAllSwitch").exists() }).toEqual(
        { name, shown },
      );
      wrapper.unmount();
    }
  });

  test("turning it on sends this filter in matchAll and unticks None", async () => {
    const { wrapper } = mountSubmenu({
      filters: { characters: [-1, 1], matchAll: ["tags"] },
      dynamic: { characters: SPIDEY },
    });
    wrapper.vm.onMatchAll(true);
    await flushPromises();
    expect(wrapper.emitted("selected").at(-1)[0]).toEqual({
      filters: { matchAll: ["tags", "characters"], characters: [1] },
    });
  });

  test("turning it off removes only this filter", async () => {
    const { wrapper } = mountSubmenu({
      filters: { characters: [1], matchAll: ["characters", "tags"] },
      dynamic: { characters: SPIDEY },
    });
    wrapper.vm.onMatchAll(false);
    await flushPromises();
    expect(wrapper.emitted("selected").at(-1)[0]).toEqual({
      filters: { matchAll: ["tags"] },
    });
  });

  test("says why rows dim while it is on", () => {
    // Stated, not defaulted: earlier tests leak into the shared defaults.
    const off = mountSubmenu({
      filters: { matchAll: [] },
      dynamic: { characters: SPIDEY },
    });
    expect(off.wrapper.find(".matchAllHint").exists()).toBe(false);
    off.wrapper.unmount();
    const on = mountSubmenu({
      filters: { matchAll: ["characters"] },
      dynamic: { characters: SPIDEY },
    });
    expect(on.wrapper.find(".matchAllHint").text()).toBeTruthy();
  });

  test("under All, a tick refreshes the open list once the page reloads", async () => {
    const { wrapper, browserStore } = mountSubmenu({
      filters: { characters: [], matchAll: ["characters"] },
      dynamic: { characters: SPIDEY },
    });
    wrapper.vm.onSelected([1]);
    await flushPromises();
    expect(browserStore.loadFilterChoices).not.toHaveBeenCalled();
    browserStore.page = { mtime: 2 };
    await flushPromises();
    expect(browserStore.loadFilterChoices).toHaveBeenCalledExactlyOnceWith(
      "characters",
    );
  });

  test("Clear Filter leaves the switch as set", async () => {
    const { wrapper, browserStore } = mountSubmenu({
      filters: { characters: [1], matchAll: ["characters"] },
      dynamic: { characters: SPIDEY },
    });
    await wrapper.find(".clearFilter").trigger("click");
    await flushPromises();
    expect(browserStore.clearOneFilter).toHaveBeenCalledWith("characters");
    expect(browserStore.setSettings).not.toHaveBeenCalled();
    expect(browserStore.settings.filters.matchAll).toEqual(["characters"]);
  });
});
