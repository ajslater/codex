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
 *     prepend/append slot rows ("Clear All Filters", the filter
 *     sub-menus) with no keyboard route in. ``onMenuKeydownCapture`` hands
 *     those two edge steps to the adjacent slot row instead.
 *
 * Shelves folded into reading lists, whose filter is an ordinary
 * sub-menu: there is no Shelves row.
 *
 * Real Vuetify is mounted so the overlay, list and its keyboard handlers
 * are the ones that ship; store actions are stubbed by createTestingPinia.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
} from "vitest";

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

async function mountOpenMenu({
  filters = {},
  dynamic = { characters: true },
  choicesStale = false,
} = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { pk: 1 } },
      browser: {
        filterMode: "base",
        choicesStale,
        // A non-default bookmark makes the "Clear All Filters" row render.
        settings: { filters: { bookmark: "UNREAD", ...filters } },
        choices: { dynamic },
      },
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

const CHARACTERS = Object.freeze([
  { pk: 1, name: "Spider-Man" },
  { pk: 2, name: "Iron Man" },
]);

async function openCharacters(options = {}) {
  const opened = await mountOpenMenu({
    dynamic: { characters: CHARACTERS },
    ...options,
  });
  const row = [...opened.content.querySelectorAll(".v-list-item")].find(
    (candidate) => candidate.textContent.includes("Characters"),
  );
  row.click();
  await flushPromises();
  const choice = (title) =>
    [...opened.content.querySelectorAll("[role=menuitemcheckbox]")].find(
      (candidate) => candidate.textContent.includes(title),
    );
  return { ...opened, choice };
}

const key = (el, name) =>
  el.dispatchEvent(
    new KeyboardEvent("keydown", {
      key: name,
      bubbles: true,
      cancelable: true,
    }),
  );

describe("BrowserFilterBySelect — ticking in a sub-menu", () => {
  test("a tick applies and leaves the menu open on its sub-menu", async () => {
    const { wrapper, browserStore, choice } = await openCharacters();
    choice("Iron Man").click();
    await flushPromises();
    expect(browserStore.tickFilters).toHaveBeenCalledWith({ characters: [2] });
    expect(browserStore.setSettings).not.toHaveBeenCalled();
    expect(wrapper.vm.menu).toBe(true);
    expect(browserStore.filterMode).toBe("characters");
  });

  test("a letter key on a choice row stays in the sub-menu", async () => {
    const { content, wrapper, browserStore, choice } = await openCharacters();
    const reached = [];
    content.addEventListener("keydown", (event) => {
      reached.push(event.key);
    });
    key(choice("Spider-Man"), "a");
    key(choice("Spider-Man"), "ArrowDown");
    key(choice("Spider-Man"), "Escape");
    await flushPromises();
    expect(reached).toEqual(["ArrowDown", "Escape"]);
    expect(browserStore.setSettings).not.toHaveBeenCalled();
    expect(wrapper.vm.menu).toBe(false);
  });

  test("back at the filter list, stale choices are fetched again", async () => {
    const { content, browserStore } = await openCharacters({
      choicesStale: true,
    });
    browserStore.loadAvailableFilterChoices.mockClear();
    content.querySelector(".filterHeaderTitle").click();
    await flushPromises();
    expect(browserStore.filterMode).toBe("base");
    expect(browserStore.loadAvailableFilterChoices).toHaveBeenCalledOnce();
  });

  test("back at the filter list, fresh choices are kept", async () => {
    const { content, browserStore } = await openCharacters();
    browserStore.loadAvailableFilterChoices.mockClear();
    content.querySelector(".filterHeaderTitle").click();
    await flushPromises();
    expect(browserStore.loadAvailableFilterChoices).not.toHaveBeenCalled();
  });

  test("in a sub-menu, Clear All Filters gives way to its own Clear Filter", async () => {
    const { content } = await openCharacters({
      filters: { characters: [1] },
    });
    const titles = [...content.querySelectorAll(".clearFilter")].map((row) =>
      row.textContent.trim(),
    );
    expect(titles).toEqual(["Clear Filter"]);
  });

  test("the filter list shows how many values are ticked", async () => {
    const { content } = await mountOpenMenu({
      filters: { characters: [1, 2] },
      dynamic: { characters: CHARACTERS },
    });
    const row = content.querySelector(".filterTickedCount");
    expect(row.textContent.trim()).toBe("2");
  });
});

describe("BrowserFilterBySelect — arrow keys in a sub-menu", () => {
  /*
   * Vuetify's list walks only rendered rows (``offsetParent``), and
   * happy-dom renders nothing, so its arrow keys would move no focus at
   * all. Give every element its parent as ``offsetParent`` while these
   * run, so both nested lists really handle the key.
   */
  const descriptor = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    "offsetParent",
  );
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, "offsetParent", {
      configurable: true,
      get() {
        return this.parentElement;
      },
    });
  });
  afterEach(() => {
    if (descriptor) {
      Object.defineProperty(HTMLElement.prototype, "offsetParent", descriptor);
    }
  });

  test("an arrow key on a choice row steps one row", async () => {
    const { choice } = await openCharacters();
    choice("Iron Man").focus();
    key(choice("Iron Man"), "ArrowDown");
    expect(document.activeElement).toBe(choice("Spider-Man"));
    key(choice("Spider-Man"), "ArrowUp");
    expect(document.activeElement).toBe(choice("Iron Man"));
  });

  test("an arrow key off the end of the choices leaves them, not wraps", async () => {
    const { content, choice } = await openCharacters();
    choice("Iron Man").focus();
    key(choice("Iron Man"), "ArrowUp");
    expect(document.activeElement).not.toBe(choice("Spider-Man"));
    expect(document.activeElement.getAttribute("role")).not.toBe(
      "menuitemcheckbox",
    );
    expect(content.contains(document.activeElement)).toBe(true);
  });
});

describe("BrowserFilterBySelect — the store knows the menu is open", () => {
  test("opening and closing tell the store", async () => {
    const { wrapper, browserStore } = await mountOpenMenu();
    expect(browserStore.setFilterMenuOpen).toHaveBeenLastCalledWith(true);
    wrapper.vm.menu = false;
    await flushPromises();
    expect(browserStore.setFilterMenuOpen).toHaveBeenLastCalledWith(false);
  });

  test("leaving the page with the menu open tells the store it closed", async () => {
    const { wrapper, browserStore } = await mountOpenMenu();
    wrapper.unmount();
    wrappers.length = 0;
    expect(browserStore.setFilterMenuOpen).toHaveBeenLastCalledWith(false);
  });
});

const arrow = (el, key) =>
  el.dispatchEvent(
    new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }),
  );

describe("BrowserFilterBySelect — keyboard reach into the slot rows", () => {
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
    expect(content.contains(document.activeElement)).toBe(true);
  });

  test("ArrowDown off the last row steps to the first filter sub-menu", async () => {
    const { content, rows } = await mountOpenMenu();
    const last = rows.at(-1);

    last.focus();
    arrow(last, "ArrowDown");

    // Not a bookmark row: it stepped past the list instead of wrapping.
    expect(content.contains(document.activeElement)).toBe(true);
    expect(document.activeElement.hasAttribute("aria-posinset")).toBe(false);
  });

  test("there is no Shelves row", async () => {
    const { content, wrapper } = await mountOpenMenu({
      filters: { readingLists: [4] },
    });
    expect(content.textContent).not.toContain("Shelves");
    expect(content.textContent).not.toContain("Favorites Only");
    // A selected list filter is an ordinary choices sub-menu.
    expect(wrapper.vm.dynamicChoiceNames).toEqual([
      "characters",
      "readingLists",
    ]);
  });

  test("the Any/All switch is no sub-menu", async () => {
    const { wrapper } = await mountOpenMenu({
      filters: { matchAll: ["characters"] },
    });
    expect(wrapper.vm.dynamicChoiceNames).toContain("characters");
    expect(wrapper.vm.dynamicChoiceNames).not.toContain("matchAll");
  });

  test("a picked reading list kind is an ordinary sub-menu", async () => {
    const { content, wrapper } = await mountOpenMenu({
      filters: { readingListKind: ["mine"] },
    });
    expect(wrapper.vm.dynamicChoiceNames).toContain("readingListKind");
    expect(content.textContent).toContain("Reading List Kind");
  });

  test("Clear All Filters resets the Match all ticked switch", async () => {
    const { wrapper, browserStore } = await mountOpenMenu({
      filters: { characters: [1], matchAll: ["characters"] },
    });
    await wrapper.vm.onClear();
    const sent = browserStore.setSettings.mock.calls.at(-1)[0];
    expect(sent.filters.matchAll).toStrictEqual([]);
  });

  test("Clear All Filters clears the kind to an empty list", async () => {
    const { wrapper, browserStore } = await mountOpenMenu({
      filters: { readingListKind: ["tags"] },
    });
    await wrapper.vm.onClear();
    const sent = browserStore.setSettings.mock.calls.at(-1)[0];
    expect(sent.filters.readingListKind).toStrictEqual([]);
  });
});
