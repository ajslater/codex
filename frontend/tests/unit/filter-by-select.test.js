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

async function mountOpenMenu({ filters = {} } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { pk: 1 } },
      browser: {
        filterMode: "base",
        // A non-default bookmark makes the "Clear All Filters" row render.
        settings: { filters: { bookmark: "UNREAD", ...filters } },
        choices: { dynamic: { characters: true } },
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
});
