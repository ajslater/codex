/*
 * Tests for ``filter-by-select.vue`` — the browser's "filter by" menu.
 *
 * Both cases guard behavior that Vuetify 4.2 changed underneath this
 * component:
 *   - ``useSelectionMenu.closeOnSelect()`` now bails when ``menuProps``
 *     carries ``closeOnContentClick: false``, so ``onSubMenuSelected`` is
 *     the only thing left that closes this menu after a pick.
 *   - the list keydown capture added by ``useScrolling`` wraps from either
 *     end of the bookmark rows and stops propagation, which used to strand
 *     prepend/append slot rows ("Clear All Filters", "Shelves", the
 *     filter sub-menus) with no keyboard route in. ``onMenuKeydownCapture``
 *     hands those two edge steps to the adjacent slot row instead.
 *
 * It also covers the "Shelves" sub-menu, which lists the signed-in
 * user's shelves from the shelves store as checkboxes that set
 * ``filters.shelves``.
 *
 * Real Vuetify is mounted so the overlay, list and its keyboard handlers
 * are the ones that ship; store actions are stubbed by createTestingPinia.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test } from "vitest";

import FilterBySelect from "@/components/browser/toolbars/top/filter-by-select.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

beforeAll(() => {
  /*
   * VOverlay's connected location strategy reads the bare global; happy-dom
   * has no visual viewport, so the menu never positions without this.
   */
  globalThis.visualViewport ??= {
    width: 1024,
    height: 768,
    offsetLeft: 0,
    offsetTop: 0,
    scale: 1,
    addEventListener() {},
    removeEventListener() {},
  };
});

const wrappers = [];

const SHELVES = [
  { pk: 4, name: "Favorites", items: {} },
  { pk: 9, name: "Want to Read", items: {} },
];

async function mountOpenMenu({
  loggedIn = true,
  shelves = SHELVES,
  filters = {},
} = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: loggedIn ? { pk: 1 } : undefined },
      browser: {
        filterMode: "base",
        // A non-default bookmark makes the "Clear All Filters" row render.
        settings: { filters: { bookmark: "UNREAD", ...filters } },
        choices: { dynamic: { characters: true } },
      },
      shelves: { shelves, hydrated: true },
    },
  });
  const wrapper = mount(FilterBySelect, {
    attachTo: document.body,
    global: { plugins: [pinia, vuetify] },
  });
  wrappers.push(wrapper);
  wrapper.vm.menu = true;
  await flushPromises();
  const content = document.querySelector(".v-overlay__content");
  const rows = [...content.querySelectorAll("[aria-posinset]")];
  return { wrapper, content, rows, browserStore: useBrowserStore() };
}

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
});

describe("BrowserFilterBySelect — closing on select", () => {
  test("picking a bookmark applies it and closes the menu", async () => {
    const { wrapper, rows, browserStore } = await mountOpenMenu();
    const inProgress = rows.find((row) =>
      row.textContent.includes("In Progress"),
    );

    inProgress.click();
    await flushPromises();

    expect(browserStore.setSettings).toHaveBeenCalledWith({
      filters: { bookmark: "IN_PROGRESS" },
    });
    expect(wrapper.vm.menu).toBe(false);
  });
});

const arrow = (el, key) =>
  el.dispatchEvent(
    new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }),
  );

describe("BrowserFilterBySelect — keyboard reach into the slot rows", () => {
  test("ArrowDown off the last bookmark row lands on Shelves", async () => {
    const { content, rows } = await mountOpenMenu();
    const last = rows.at(-1);

    last.focus();
    arrow(last, "ArrowDown");

    expect(document.activeElement).toBe(
      content.querySelector(".shelvesFilter"),
    );
  });

  test("ArrowUp off the first bookmark row lands on Clear All Filters", async () => {
    const { content, rows } = await mountOpenMenu();
    const first = rows[0];

    first.focus();
    arrow(first, "ArrowUp");

    expect(document.activeElement).toBe(content.querySelector(".clearFilter"));
  });

  test("mid-list rows are left to Vuetify", async () => {
    const { content, rows } = await mountOpenMenu();
    const middle = rows[1];
    let reached = 0;
    middle.addEventListener("keydown", () => (reached += 1));

    middle.focus();
    arrow(middle, "ArrowDown");

    /*
     * Interception stops the event at the overlay content, so an untouched
     * event is one that still reaches the row Vuetify navigates from.
     */
    expect(reached).toBe(1);
    expect(document.activeElement).not.toBe(
      content.querySelector(".shelvesFilter"),
    );
  });

  test("logged out, the last row steps to the first filter sub-menu", async () => {
    const { content, rows } = await mountOpenMenu({ loggedIn: false });
    const last = rows.at(-1);

    last.focus();
    arrow(last, "ArrowDown");

    // Not a bookmark row: it stepped past the list instead of wrapping.
    expect(content.querySelector(".shelvesFilter")).toBeNull();
    expect(content.contains(document.activeElement)).toBe(true);
    expect(document.activeElement.hasAttribute("aria-posinset")).toBe(false);
  });
});

const shelfRows = (content) => [
  ...content.querySelectorAll(".shelvesFilterRow"),
];

async function openShelves(options) {
  const mounted = await mountOpenMenu(options);
  mounted.content.querySelector(".shelvesFilter").click();
  await flushPromises();
  return mounted;
}

describe("BrowserFilterBySelect — shelves sub-menu", () => {
  test("there is no Favorites Only row", async () => {
    const { content } = await mountOpenMenu();
    expect(content.textContent).not.toContain("Favorites Only");
  });

  test("hidden when the user has no shelves", async () => {
    const { content } = await mountOpenMenu({ shelves: [] });
    expect(content.querySelector(".shelvesFilter")).toBeNull();
  });

  test("selected shelves never render as a choices sub-menu", async () => {
    const { wrapper } = await mountOpenMenu({ filters: { shelves: [4] } });
    expect(wrapper.vm.dynamicChoiceNames).toEqual(["characters"]);
  });

  test("lists the user's shelves with the selected ones ticked", async () => {
    const { content, browserStore } = await openShelves({
      filters: { shelves: [9] },
    });
    expect(browserStore.filterMode).toBe("shelves");
    const rows = shelfRows(content);
    expect(rows.map((row) => row.textContent.trim())).toEqual([
      "Favorites",
      "Want to Read",
    ]);
    expect(rows.map((row) => row.getAttribute("aria-checked"))).toEqual([
      "false",
      "true",
    ]);
  });

  test("ticking a shelf adds it to filters.shelves and keeps the menu open", async () => {
    const { wrapper, content, browserStore } = await openShelves({
      filters: { shelves: [9] },
    });

    shelfRows(content)[0].click();
    await flushPromises();

    expect(browserStore.setSettings).toHaveBeenCalledExactlyOnceWith({
      filters: { shelves: [9, 4] },
    });
    expect(wrapper.vm.menu).toBe(true);
    expect(browserStore.filterMode).toBe("shelves");
  });

  test("unticking a shelf removes it from filters.shelves", async () => {
    const { content, browserStore } = await openShelves({
      filters: { shelves: [4, 9] },
    });

    shelfRows(content)[1].click();
    await flushPromises();

    expect(browserStore.setSettings).toHaveBeenCalledExactlyOnceWith({
      filters: { shelves: [4] },
    });
  });

  test("Clear Filter empties filters.shelves", async () => {
    const { content, browserStore } = await openShelves({
      filters: { shelves: [4] },
    });

    content.querySelector(".clearShelvesFilter").click();
    await flushPromises();

    expect(browserStore.setSettings).toHaveBeenCalledExactlyOnceWith({
      filters: { shelves: [] },
    });
  });

  test("ticking a shelf reloads the filter choices", async () => {
    /*
     * The page reload that a tick triggers clears ``choices.dynamic``;
     * without a reload every other filter row showed a progress bar until
     * the menu was reopened.
     */
    const { content, browserStore } = await openShelves({
      filters: { shelves: [9] },
    });

    shelfRows(content)[0].click();
    await flushPromises();

    expect(browserStore.loadAvailableFilterChoices).toHaveBeenCalledOnce();
    expect(browserStore.setSettings.mock.invocationCallOrder[0]).toBeLessThan(
      browserStore.loadAvailableFilterChoices.mock.invocationCallOrder[0],
    );
  });

  test("Clear Filter reloads the filter choices", async () => {
    const { content, browserStore } = await openShelves({
      filters: { shelves: [4] },
    });

    content.querySelector(".clearShelvesFilter").click();
    await flushPromises();

    expect(browserStore.loadAvailableFilterChoices).toHaveBeenCalledOnce();
  });

  test("Clear All Filters also empties filters.shelves", async () => {
    const { wrapper, browserStore } = await mountOpenMenu({
      filters: { shelves: [4] },
    });

    await wrapper.vm.onClear();

    expect(browserStore.clearFilters).toHaveBeenCalled();
    const cleared = browserStore.setSettings.mock.calls.at(-1)[0];
    expect(cleared.filters.shelves).toEqual([]);
    expect(cleared.filters).not.toHaveProperty("favorite");
  });
});
