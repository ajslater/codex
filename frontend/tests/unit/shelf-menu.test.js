/*
 * Unit tests for ``shelf-menu.vue`` — the shelf button and its menu,
 * shared by browser cards and table cells (single ``pk``), the metadata
 * toolbar (``pks``) and the multi-select toolbar (``targets`` spanning
 * several collection types). Covers the target normalization, the
 * "every target shelved" accent, the checked / indeterminate rows, that
 * a row click dispatches one bulk membership change, the "New shelf…"
 * flow with its suggestions and the server's reason for a refusal, that
 * Enter mid IME composition submits nothing, and that anonymous sessions
 * get nothing.
 * Real Vuetify is mounted so the menu and its rows are the ones that
 * ship; store actions are stubbed by createTestingPinia so calls can be
 * asserted.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test } from "vitest";

import { APIError } from "@/api/v4/base";
import ShelfMenu from "@/components/shelf-menu.vue";
import ShelfNameInput from "@/components/shelf-name-input.vue";
import vuetify from "@/plugins/vuetify";
import { useShelvesStore } from "@/stores/shelves";

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

const shelf = (pk, name, items = {}) => ({
  pk,
  name,
  items: Object.fromEntries(
    [
      "publishers",
      "imprints",
      "series",
      "volumes",
      "folders",
      "arcs",
      "comics",
    ].map((collection) => [collection, new Set(items[collection] || [])]),
  ),
});

const DUPLICATE = "You already have a shelf with that name.";
const refusal = () =>
  new APIError({ status: "400", title: "Bad Request", detail: DUPLICATE }, 400);

const SHELVES = () => [
  shelf(1, "Favorites", { series: [1, 2], comics: [42] }),
  shelf(2, "Want to Read", { series: [1] }),
];

const wrappers = [];

function mountMenu(props, { loggedIn = true, shelves = SHELVES() } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: loggedIn ? { pk: 1 } : null },
      shelves: { shelves },
    },
    stubActions: true,
  });
  const wrapper = mount(ShelfMenu, {
    attachTo: document.body,
    global: { plugins: [pinia, vuetify] },
    props,
  });
  wrappers.push(wrapper);
  return { wrapper, shelvesStore: useShelvesStore() };
}

async function openMenu(wrapper) {
  wrapper.vm.menu = true;
  await flushPromises();
  return document.querySelector(".shelfMenu");
}

const location = (wrapper) =>
  wrapper.findComponent({ name: "VMenu" }).props("location");

const rowTitles = (content) =>
  [...content.querySelectorAll(".shelfMenuRow")].map((row) =>
    row.textContent.trim(),
  );

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
});

describe("ShelfMenu — targets", () => {
  test("a single pk normalizes to one numeric target", () => {
    const { wrapper } = mountMenu({ collection: "comics", pk: "42" });
    expect(wrapper.vm.targetMap).toEqual({ comics: [42] });
    expect(wrapper.vm.disabled).toBe(false);
  });

  test("pks win over pk and normalize to numbers", () => {
    const { wrapper } = mountMenu({ collection: "series", pks: ["1", "2"] });
    expect(wrapper.vm.targetMap).toEqual({ series: [1, 2] });
    expect(wrapper.vm.title).toBe("Shelves and reading lists for 2 items");
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

describe("ShelfMenu — button", () => {
  test("accented only when every target is on some shelf", () => {
    const allOn = mountMenu({ collection: "series", pks: [1, 2] });
    expect(allOn.wrapper.vm.on).toBe(true);
    expect(allOn.wrapper.find("button").classes()).toContain("shelfMenuOn");

    const mixed = mountMenu({ collection: "series", pks: [1, 2, 3] });
    expect(mixed.wrapper.vm.on).toBe(false);
    expect(mixed.wrapper.find("button").classes()).not.toContain("shelfMenuOn");
  });

  test("the call site's class and id land on the button", () => {
    const { wrapper } = mountMenu(
      { collection: "comics", pk: 42 },
      { shelves: [] },
    );
    const mounted = mount(ShelfMenu, {
      global: { plugins: [wrapper.vm.$pinia, vuetify] },
      props: { collection: "comics", pk: 42 },
      attrs: { class: "readerShelfMenu", id: "shelfButton" },
    });
    wrappers.push(mounted);
    const button = mounted.find("button");
    expect(button.classes()).toContain("readerShelfMenu");
    expect(button.attributes("id")).toBe("shelfButton");
  });

  test("the menu hangs toward the end unless the call site says otherwise", () => {
    const { wrapper: byDefault } = mountMenu({ collection: "comics", pk: 42 });
    expect(location(byDefault)).toBe("bottom end");

    // A browser card's action menu opens it beside itself, as a submenu.
    const { wrapper: submenu } = mountMenu({
      collection: "comics",
      pk: 42,
      location: "end",
    });
    expect(location(submenu)).toBe("end");
  });

  test("anonymous sessions get no shelf button at all", () => {
    const { wrapper } = mountMenu(
      { collection: "series", pk: 1 },
      { loggedIn: false },
    );
    expect(wrapper.find("button").exists()).toBe(false);
  });
});

describe("ShelfMenu — shelf rows", () => {
  test("lists every shelf under a Shelves section", async () => {
    const { wrapper } = mountMenu({ collection: "series", pk: 1 });
    const content = await openMenu(wrapper);
    expect(content.querySelector(".menuSectionTitle").textContent).toBe(
      "Shelves",
    );
    expect(rowTitles(content)).toEqual(["Favorites", "Want to Read"]);
  });

  test("checked when all targets are on it, indeterminate when some", async () => {
    const { wrapper } = mountMenu({ collection: "series", pks: [1, 2] });
    expect(wrapper.vm.shelfRows.map((row) => row.state)).toEqual([
      "all",
      "some",
    ]);
    const content = await openMenu(wrapper);
    const rows = [...content.querySelectorAll(".shelfMenuRow")];
    expect(rows.map((row) => row.getAttribute("aria-checked"))).toEqual([
      "true",
      "mixed",
    ]);
    expect(rows[0].querySelector("input").checked).toBe(true);
    expect(rows[1].querySelector("input").indeterminate).toBe(true);
  });

  test("clicking a checked row takes every target off that shelf", async () => {
    const { wrapper, shelvesStore } = mountMenu({
      collection: "series",
      pks: [1, 2],
    });
    const content = await openMenu(wrapper);
    content.querySelector(".shelfMenuRow").click();
    expect(shelvesStore.setTargetsMembership).toHaveBeenCalledExactlyOnceWith(
      1,
      { series: [1, 2] },
      false,
    );
    // Stays open so more shelves can be ticked.
    expect(wrapper.vm.menu).toBe(true);
  });

  test("clicking a mixed or empty row puts every target on it", async () => {
    const { wrapper, shelvesStore } = mountMenu({
      targets: { series: [1, 2], comics: [42] },
    });
    const content = await openMenu(wrapper);
    content.querySelectorAll(".shelfMenuRow")[1].click();
    expect(shelvesStore.setTargetsMembership).toHaveBeenCalledExactlyOnceWith(
      2,
      { series: [1, 2], comics: [42] },
      true,
    );
  });
});

describe("ShelfMenu — new shelf", () => {
  test("the New shelf row reveals the name input", async () => {
    const { wrapper } = mountMenu({ collection: "comics", pk: 42 });
    const content = await openMenu(wrapper);
    expect(wrapper.findComponent(ShelfNameInput).exists()).toBe(false);

    content.querySelector(".shelfMenuNew").click();
    await flushPromises();

    const input = wrapper.findComponent(ShelfNameInput);
    expect(input.exists()).toBe(true);
    // "Favorites" and "Want to Read" already exist, so aren't suggested.
    expect(input.vm.suggestions).toEqual(["Reading Now"]);
  });

  test("creating a shelf adds the targets to it", async () => {
    const { wrapper, shelvesStore } = mountMenu({
      collection: "comics",
      pk: 42,
    });
    shelvesStore.createShelf.mockResolvedValue(shelf(9, "Finished"));
    await openMenu(wrapper);
    wrapper.vm.creating = true;
    await flushPromises();

    wrapper.findComponent(ShelfNameInput).vm.$emit("submit", "Finished");
    await flushPromises();

    expect(shelvesStore.createShelf).toHaveBeenCalledWith("Finished");
    expect(shelvesStore.setTargetsMembership).toHaveBeenCalledExactlyOnceWith(
      9,
      { comics: [42] },
      true,
    );
    expect(wrapper.vm.creating).toBe(false);
  });

  test("a refused create keeps the input open with the server's reason", async () => {
    const { wrapper, shelvesStore } = mountMenu({
      collection: "comics",
      pk: 42,
    });
    shelvesStore.createShelf.mockRejectedValue(refusal());
    await openMenu(wrapper);
    wrapper.vm.creating = true;
    await flushPromises();

    wrapper.findComponent(ShelfNameInput).vm.$emit("submit", "Finished");
    await flushPromises();

    expect(shelvesStore.setTargetsMembership).not.toHaveBeenCalled();
    expect(wrapper.vm.creating).toBe(true);
    expect(wrapper.vm.createError).toBe(DUPLICATE);
    expect(wrapper.findComponent(ShelfNameInput).vm.shownError).toBe(DUPLICATE);
  });

  test("New shelf again drops the last attempt's error", async () => {
    const { wrapper } = mountMenu({ collection: "comics", pk: 42 });
    const content = await openMenu(wrapper);
    wrapper.vm.creating = true;
    wrapper.vm.createError = DUPLICATE;
    await flushPromises();

    wrapper.findComponent(ShelfNameInput).vm.$emit("cancel");
    await flushPromises();
    content.querySelector(".shelfMenuNew").click();
    await flushPromises();

    expect(wrapper.findComponent(ShelfNameInput).vm.shownError).toBe("");
  });
});

function mountInput(existingNames = []) {
  const wrapper = mount(ShelfNameInput, {
    global: { plugins: [vuetify] },
    props: { existingNames, autofocus: false },
  });
  wrappers.push(wrapper);
  return wrapper;
}

describe("ShelfNameInput", () => {
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
    await wrapper.find(".shelfNameSubmit").trigger("click");
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
    expect(wrapper.vm.shownError).toContain("already exists");
  });
});
