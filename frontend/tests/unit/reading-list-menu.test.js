/*
 * ``reading-list-menu.vue``: the list button and its menu, shared by
 * browser cards and table cells (single ``pk``), the metadata dialog
 * (``pks``) and the multi-select toolbar (``targets`` spanning several
 * collection types). Ported from the shelf menu tests when shelves folded
 * into reading lists. Covers the target normalization, the "every target
 * listed" accent, the checked / mixed rows that toggle and keep the menu
 * open, global lists marked, a list never offered to itself, the find
 * field, the "New reading list…" flow with its suggestions and the
 * server's reason for a refusal, that Enter mid IME composition submits
 * nothing, and that anonymous sessions get nothing.
 * Real Vuetify is mounted; store actions are stubbed by createTestingPinia
 * so calls can be asserted.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test } from "vitest";

import { APIError } from "@/api/v4/base";
import ListNameInput from "@/components/list-name-input.vue";
import ReadingListMenu from "@/components/reading-list-menu.vue";
import vuetify from "@/plugins/vuetify";
import {
  LIST_ITEM_COLLECTIONS,
  useReadingListsStore,
} from "@/stores/reading-lists";

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

const list = (
  pk,
  name,
  { items = {}, personal = true, editable = true } = {},
) => ({
  pk,
  name,
  personal,
  editable,
  count: 0,
  items: Object.fromEntries(
    LIST_ITEM_COLLECTIONS.map((collection) => [
      collection,
      new Set(items[collection] || []),
    ]),
  ),
});

const DUPLICATE = "You already have a reading list with that name.";
const refusal = () =>
  new APIError({ status: "400", title: "Bad Request", detail: DUPLICATE }, 400);

const LISTS = () => [
  list(1, "Favorites", { items: { series: [1, 2], comics: [42] } }),
  list(2, "Want to Read", { items: { series: [1] } }),
  list(3, "Civil War", { personal: false }),
  list(4, "Theirs", { personal: false, editable: false }),
];

const wrappers = [];

function mountMenu(
  props,
  { loggedIn = true, lists = LISTS(), loaded = true } = {},
) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: loggedIn ? { pk: 1 } : null },
      readingLists: { myLists: lists, myListsLoaded: loaded },
    },
    stubActions: true,
  });
  const wrapper = mount(ReadingListMenu, {
    attachTo: document.body,
    global: { plugins: [pinia, vuetify] },
    props,
  });
  wrappers.push(wrapper);
  return { wrapper, store: useReadingListsStore() };
}

async function openMenu(wrapper) {
  wrapper.vm.menu = true;
  await flushPromises();
  return document.querySelector(".listMenu");
}

const location = (wrapper) =>
  wrapper.findComponent({ name: "VMenu" }).props("location");

const rowTitles = (content) =>
  [...content.querySelectorAll(":scope .listMenuRow .v-list-item-title")].map(
    (row) => row.textContent.trim(),
  );

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
});

describe("targets", () => {
  test("a single pk normalizes to one numeric target", () => {
    const { wrapper } = mountMenu({ collection: "comics", pk: "42" });
    expect(wrapper.vm.targetMap).toEqual({ comics: [42] });
    expect(wrapper.vm.disabled).toBe(false);
  });

  test("pks win over pk and normalize to numbers", () => {
    const { wrapper } = mountMenu({ collection: "series", pks: ["1", "2"] });
    expect(wrapper.vm.targetMap).toEqual({ series: [1, 2] });
    expect(wrapper.vm.title).toBe("Reading Lists for 2 items");
  });

  test("targets cover several collection types", () => {
    const { wrapper } = mountMenu({
      targets: { series: [1], comics: [42, 43], folders: [] },
    });
    expect(wrapper.vm.targetMap).toEqual({ series: [1], comics: [42, 43] });
    expect(wrapper.vm.targetCount).toBe(3);
  });

  test("no targets disables the button", () => {
    const { wrapper } = mountMenu({ collection: "series", pks: [] });
    expect(wrapper.vm.disabled).toBe(true);
    expect(wrapper.find("button").attributes("disabled")).toBeDefined();
  });
});

describe("button", () => {
  test("accented only when every target is in some list", () => {
    const allOn = mountMenu({ collection: "series", pks: [1, 2] });
    expect(allOn.wrapper.vm.on).toBe(true);
    expect(allOn.wrapper.find("button").classes()).toContain("listMenuOn");

    const mixed = mountMenu({ collection: "series", pks: [1, 2, 3] });
    expect(mixed.wrapper.vm.on).toBe(false);
    expect(mixed.wrapper.find("button").classes()).not.toContain("listMenuOn");
  });

  test("the call site's class and id land on the button", () => {
    const { wrapper } = mountMenu(
      { collection: "comics", pk: 42 },
      { lists: [] },
    );
    const mounted = mount(ReadingListMenu, {
      global: { plugins: [wrapper.vm.$pinia, vuetify] },
      props: { collection: "comics", pk: 42 },
      attrs: { class: "readerListMenu", id: "listButton" },
    });
    wrappers.push(mounted);
    const button = mounted.find("button");
    expect(button.classes()).toContain("readerListMenu");
    expect(button.attributes("id")).toBe("listButton");
  });

  test("the menu hangs toward the end unless the call site says otherwise", () => {
    const { wrapper: byDefault } = mountMenu({ collection: "comics", pk: 42 });
    expect(location(byDefault)).toBe("bottom end");
    const { wrapper: submenu } = mountMenu({
      collection: "comics",
      pk: 42,
      location: "end",
    });
    expect(location(submenu)).toBe("end");
  });

  test("anonymous sessions get no list button at all", () => {
    const { wrapper } = mountMenu(
      { collection: "series", pk: 1 },
      { loggedIn: false },
    );
    expect(wrapper.find("button").exists()).toBe(false);
  });
});

describe("rows", () => {
  test("lists every list the user may change, global ones marked", async () => {
    const { wrapper } = mountMenu({ collection: "series", pk: 1 });
    const content = await openMenu(wrapper);
    // No header repeating "Reading Lists": every opener already says it.
    expect(content.querySelector(".menuSectionTitle")).toBeNull();
    expect(rowTitles(content)).toEqual([
      "Favorites",
      "Want to Read",
      "Civil War",
    ]);
    const rows = [...content.querySelectorAll(".listMenuRow")];
    expect(rows[2].textContent).toContain("Global");
    expect(rows[0].textContent).not.toContain("Global");
  });

  test("a list is not offered as a place to put itself", async () => {
    const { wrapper } = mountMenu({ targets: { arcs: [1] } });
    const content = await openMenu(wrapper);
    expect(rowTitles(content)).toEqual(["Want to Read", "Civil War"]);
  });

  test("checked when all targets are in it, mixed when some", async () => {
    const { wrapper } = mountMenu({ collection: "series", pks: [1, 2] });
    expect(wrapper.vm.rows.map((row) => row.state)).toEqual([
      "all",
      "some",
      "none",
    ]);
    const content = await openMenu(wrapper);
    const rows = [...content.querySelectorAll(".listMenuRow")];
    expect(rows.map((row) => row.getAttribute("aria-checked"))).toEqual([
      "true",
      "mixed",
      "false",
    ]);
    expect(rows[0].querySelector("input").checked).toBe(true);
    expect(rows[1].querySelector("input").indeterminate).toBe(true);
  });

  test("clicking a checked row takes every target out of that list", async () => {
    const { wrapper, store } = mountMenu({ collection: "series", pks: [1, 2] });
    const content = await openMenu(wrapper);
    content.querySelector(".listMenuRow").click();
    expect(store.setTargetsMembership).toHaveBeenCalledExactlyOnceWith(
      1,
      { series: [1, 2] },
      false,
    );
    // Stays open so more lists can be ticked.
    expect(wrapper.vm.menu).toBe(true);
  });

  test("clicking a mixed or empty row puts every target in it", async () => {
    const { wrapper, store } = mountMenu({
      targets: { series: [1, 2], comics: [42] },
    });
    const content = await openMenu(wrapper);
    content.querySelectorAll(".listMenuRow")[1].click();
    expect(store.setTargetsMembership).toHaveBeenCalledExactlyOnceWith(
      2,
      { series: [1, 2], comics: [42] },
      true,
    );
  });

  test("past eight lists, a field finds one by name", async () => {
    const lists = Array.from({ length: 10 }, (_, i) =>
      list(i + 1, i === 6 ? "Secret Wars" : `List ${i + 1}`),
    );
    const { wrapper } = mountMenu({ collection: "comics", pk: 42 }, { lists });
    const content = await openMenu(wrapper);
    expect(content.querySelector(".listFilter")).not.toBeNull();
    wrapper.vm.query = "secret";
    await flushPromises();
    expect(rowTitles(content)).toEqual(["Secret Wars"]);
  });

  test("no find field for a short menu", async () => {
    const { wrapper } = mountMenu({ collection: "comics", pk: 42 });
    const content = await openMenu(wrapper);
    expect(content.querySelector(".listFilter")).toBeNull();
  });

  test("opening loads the lists when they were never loaded", async () => {
    const { wrapper, store } = mountMenu(
      { collection: "comics", pk: 42 },
      { lists: [], loaded: false },
    );
    expect(store.loadMyLists).not.toHaveBeenCalled();
    await openMenu(wrapper);
    expect(store.loadMyLists).toHaveBeenCalledOnce();
  });
});

describe("new list", () => {
  test("the New reading list row reveals the name input", async () => {
    const { wrapper } = mountMenu({ collection: "comics", pk: 42 });
    const content = await openMenu(wrapper);
    expect(wrapper.findComponent(ListNameInput).exists()).toBe(false);

    content.querySelector(".listMenuNew").click();
    await flushPromises();

    const input = wrapper.findComponent(ListNameInput);
    expect(input.exists()).toBe(true);
    // "Favorites" and "Want to Read" already exist, so aren't suggested.
    expect(input.vm.suggestions).toEqual(["Reading Now"]);
  });

  test("creating a list puts the targets in it", async () => {
    const { wrapper, store } = mountMenu({ collection: "comics", pk: 42 });
    store.createList.mockResolvedValue(list(9, "Finished"));
    await openMenu(wrapper);
    wrapper.vm.creating = true;
    await flushPromises();

    wrapper.findComponent(ListNameInput).vm.$emit("submit", "Finished");
    await flushPromises();

    expect(store.createList).toHaveBeenCalledWith("Finished");
    expect(store.setTargetsMembership).toHaveBeenCalledExactlyOnceWith(
      9,
      { comics: [42] },
      true,
    );
    expect(wrapper.vm.creating).toBe(false);
  });

  test("a refused create keeps the input open with the server's reason", async () => {
    const { wrapper, store } = mountMenu({ collection: "comics", pk: 42 });
    store.createList.mockRejectedValue(refusal());
    await openMenu(wrapper);
    wrapper.vm.creating = true;
    await flushPromises();

    wrapper.findComponent(ListNameInput).vm.$emit("submit", "Finished");
    await flushPromises();

    expect(store.setTargetsMembership).not.toHaveBeenCalled();
    expect(wrapper.vm.creating).toBe(true);
    expect(wrapper.vm.createError).toBe(DUPLICATE);
    expect(wrapper.findComponent(ListNameInput).vm.shownError).toBe(DUPLICATE);
  });

  test("New reading list again drops the last attempt's error", async () => {
    const { wrapper } = mountMenu({ collection: "comics", pk: 42 });
    const content = await openMenu(wrapper);
    wrapper.vm.creating = true;
    wrapper.vm.createError = DUPLICATE;
    await flushPromises();

    wrapper.findComponent(ListNameInput).vm.$emit("cancel");
    await flushPromises();
    content.querySelector(".listMenuNew").click();
    await flushPromises();

    expect(wrapper.findComponent(ListNameInput).vm.shownError).toBe("");
  });
});

function mountInput(existingNames = []) {
  const wrapper = mount(ListNameInput, {
    global: { plugins: [vuetify] },
    props: { existingNames, autofocus: false },
  });
  wrappers.push(wrapper);
  return wrapper;
}

describe("ListNameInput", () => {
  test("suggests the starter names", () => {
    expect(mountInput().vm.suggestions).toEqual([
      "Want to Read",
      "Favorites",
      "Reading Now",
    ]);
  });

  test("submits the trimmed name", async () => {
    const wrapper = mountInput();
    wrapper.vm.name = "  Horror  ";
    await wrapper.vm.$nextTick();
    await wrapper.find(".listNameSubmit").trigger("click");
    expect(wrapper.emitted("submit")).toEqual([["Horror"]]);
  });

  test("Enter while an IME composes submits nothing", async () => {
    const wrapper = mountInput();
    wrapper.vm.name = "Horror";
    await wrapper.vm.$nextTick();
    const input = wrapper.find("input");
    await input.trigger("keydown", { key: "Enter", isComposing: true });
    await input.trigger("keydown", { key: "Enter", keyCode: 229 });
    await flushPromises();
    expect(wrapper.emitted("submit")).toBeUndefined();

    await input.trigger("keydown", { key: "Enter" });
    await flushPromises();
    expect(wrapper.emitted("submit")).toEqual([["Horror"]]);
  });

  test("refuses blank, duplicate and over-long names", async () => {
    const wrapper = mountInput(["Horror"]);
    for (const name of ["", " ".repeat(3), "Horror", "x".repeat(129)]) {
      wrapper.vm.name = name;
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.isValid).toBe(false);
      wrapper.vm.submit();
    }
    expect(wrapper.emitted("submit")).toBeUndefined();
    wrapper.vm.name = "Horror";
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.shownError).toBe(
      "You already have a reading list with that name.",
    );
  });
});
