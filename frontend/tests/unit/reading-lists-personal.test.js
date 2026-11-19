/*
 * Personal reading lists: the "Reading Lists" section of the shelf menu
 * (``reading-list-menu-section.vue``) and the settings drawer's "Reading
 * Lists" block (``browser-settings-reading-lists.vue``). The menu adds a
 * selection to a list or to a new one; the drawer lists only the user's
 * own lists and opens, edits, renames, duplicates and deletes them. Real
 * Vuetify is mounted; store actions are stubbed by createTestingPinia so
 * calls can be asserted.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test } from "vitest";

import BrowserSettingsReadingLists from "@/components/browser/drawer/browser-settings-reading-lists.vue";
import NameListEditor from "@/components/name-list-editor.vue";
import ReadingListMenuSection from "@/components/reading-list-menu-section.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";
import { useReadingListsStore } from "@/stores/reading-lists";

beforeAll(() => {
  // VOverlay reads the bare global; happy-dom has no visual viewport.
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

const LISTS = () => [
  { pk: 1, name: "Civil War", personal: false, count: 5, editable: true },
  { pk: 2, name: "My Spidey", personal: true, count: 3, editable: true },
];

const TARGETS = Object.freeze({ series: [4], comics: [42] });

const wrappers = [];

function mountWith(component, { loggedIn = true, lists = LISTS(), props }) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: loggedIn ? { pk: 1 } : null },
      readingLists: { myLists: lists, myListsLoaded: true },
    },
    stubActions: true,
  });
  const wrapper = mount(component, {
    attachTo: document.body,
    global: {
      plugins: [pinia, vuetify],
      stubs: { ReviewDialog: true },
    },
    props,
  });
  wrappers.push(wrapper);
  return { wrapper, store: useReadingListsStore() };
}

const mountSection = () =>
  mountWith(ReadingListMenuSection, { props: { targets: TARGETS } });

const mountBlock = (options = {}) =>
  mountWith(BrowserSettingsReadingLists, options);

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
});

describe("ReadingListMenuSection", () => {
  test("lists every list the user may add to, global ones marked", () => {
    const { wrapper } = mountSection();
    const rows = wrapper.findAll(".v-list-item");
    const titles = rows.map((row) => row.find(".v-list-item-title").text());
    expect(titles).toEqual(["Civil War", "My Spidey", "New reading list…"]);
    expect(rows[0].text()).toContain("Global");
    expect(rows[1].text()).not.toContain("Global");
  });

  test("no find field for a short menu", () => {
    const { wrapper } = mountSection();
    expect(wrapper.find(".listFilter").exists()).toBe(false);
  });

  test("past eight lists, a field finds one by name", async () => {
    const lists = Array.from({ length: 10 }, (_, i) => ({
      pk: i + 1,
      name: i === 6 ? "Secret Wars" : `List ${i + 1}`,
      personal: true,
      count: 1,
      editable: true,
    }));
    const { wrapper } = mountWith(ReadingListMenuSection, {
      lists,
      props: { targets: TARGETS },
    });
    expect(wrapper.find(".listFilter").exists()).toBe(true);
    wrapper.vm.query = "secret";
    await wrapper.vm.$nextTick();
    const titles = wrapper
      .findAll(".readingListMenuList .v-list-item-title")
      .map((title) => title.text());
    expect(titles).toEqual(["Secret Wars", "New reading list…"]);
  });

  test("a row click adds the targets and closes the menu", async () => {
    const { wrapper, store } = mountSection();
    await wrapper.findAll(".v-list-item")[1].trigger("click");
    await flushPromises();
    expect(store.addTargets).toHaveBeenCalledWith(2, TARGETS);
    expect(wrapper.emitted("done")).toHaveLength(1);
  });

  test("a new list is created, then the targets added to it", async () => {
    const { wrapper, store } = mountSection();
    store.createList.mockResolvedValue({ pk: 9, name: "Fresh" });
    wrapper.vm.creating = true;
    wrapper.vm.name = "  Fresh ";
    await wrapper.vm.create();
    expect(store.createList).toHaveBeenCalledWith("Fresh");
    expect(store.addTargets).toHaveBeenCalledWith(9, TARGETS);
    expect(wrapper.vm.creating).toBe(false);
    expect(wrapper.emitted("done")).toHaveLength(1);
  });

  test("a failed create adds nothing and stays open", async () => {
    const { wrapper, store } = mountSection();
    store.createList.mockResolvedValue();
    wrapper.vm.name = "Fresh";
    await wrapper.vm.create();
    expect(store.addTargets).not.toHaveBeenCalled();
    expect(wrapper.emitted("done")).toBeUndefined();
  });

  test("loads the lists when they were never loaded", () => {
    const pinia = createTestingPinia({
      initialState: { readingLists: { myLists: [], myListsLoaded: false } },
      stubActions: true,
    });
    const wrapper = mount(ReadingListMenuSection, {
      global: { plugins: [pinia, vuetify] },
      props: { targets: TARGETS },
    });
    wrappers.push(wrapper);
    expect(useReadingListsStore().loadMyLists).toHaveBeenCalledOnce();
  });
});

describe("BrowserSettingsReadingLists", () => {
  test("shows only the user's own lists, with their issue counts", () => {
    const { wrapper } = mountBlock();
    const editor = wrapper.findComponent(NameListEditor);
    expect(editor.props("items").map((list) => list.name)).toEqual([
      "My Spidey",
    ]);
    expect(wrapper.text()).toContain("3 issues");
  });

  test("rename and delete call the store and refresh the grid", async () => {
    const { wrapper, store } = mountBlock();
    const editor = wrapper.findComponent(NameListEditor);
    editor.vm.$emit("rename", { pk: 2, name: "Spidey" });
    editor.vm.$emit("delete", 2);
    await flushPromises();
    expect(store.renameList).toHaveBeenCalledWith(2, "Spidey");
    expect(store.deleteList).toHaveBeenCalledWith(2);
    expect(useBrowserStore().refreshBrowserPage).toHaveBeenCalledTimes(2);
  });

  test("a duplicate refreshes the grid only when it worked", async () => {
    const { wrapper, store } = mountBlock();
    store.duplicateList.mockResolvedValueOnce({ pk: 7, name: "Copy" });
    await wrapper.vm.onDuplicate(2);
    store.duplicateList.mockResolvedValueOnce();
    await wrapper.vm.onDuplicate(2);
    expect(store.duplicateList).toHaveBeenCalledTimes(2);
    expect(useBrowserStore().refreshBrowserPage).toHaveBeenCalledOnce();
  });

  test("open routes to the list under the arcs collection", async () => {
    const { wrapper } = mountBlock();
    await wrapper.find('button[title="Open"]').trigger("click");
    expect(useBrowserStore().routeWithSettings).toHaveBeenCalledWith(
      { topCollection: "arcs" },
      {
        name: "browser",
        params: { collection: "arcs", pks: "2", page: 1 },
      },
    );
  });

  test("edit opens the entry editor without admin powers", async () => {
    const { wrapper } = mountBlock();
    await wrapper.find('button[title="Edit Issues"]').trigger("click");
    const dialog = wrapper.findComponent({ name: "ReviewDialog" });
    expect(dialog.exists()).toBe(true);
    expect(dialog.attributes("admin")).toBe("false");
    expect(wrapper.vm.showEditor).toBe(true);
  });

  test("a new list is created from the drawer", async () => {
    const { wrapper, store } = mountBlock();
    store.createList.mockResolvedValue({ pk: 3, name: "Next" });
    wrapper.vm.creating = true;
    wrapper.vm.name = "Next";
    await wrapper.vm.create();
    expect(store.createList).toHaveBeenCalledWith("Next");
    expect(wrapper.vm.creating).toBe(false);
  });

  test("anonymous sessions get nothing", () => {
    const { wrapper } = mountBlock({ loggedIn: false });
    expect(wrapper.find(".readingListsSettingsBlock").exists()).toBe(false);
  });
});
