/*
 * The settings drawer's "Reading Lists" block
 * (``browser-settings-reading-lists.vue``): only the user's own lists,
 * opened, edited, renamed, duplicated and deleted from each row's menu,
 * and new ones made with the list name input. The list menu has its own
 * tests. Real Vuetify is mounted; store actions are stubbed by
 * createTestingPinia so calls can be asserted.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test } from "vitest";

import { APIError } from "@/api/v4/base";
import BrowserSettingsReadingLists from "@/components/browser/drawer/browser-settings-reading-lists.vue";
import ListNameInput from "@/components/list-name-input.vue";
import NameListEditor from "@/components/name-list-editor.vue";
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

const mountBlock = (options = {}) =>
  mountWith(BrowserSettingsReadingLists, options);

const itemTitle = (item) =>
  item.querySelector(".v-list-item-title").textContent.trim();

async function clickMenuItem(wrapper, title) {
  const items = await openRowMenu(wrapper);
  items.find((item) => itemTitle(item) === title).click();
  await flushPromises();
}

// Open the first row's menu; its items render in an overlay on the body.
async function openRowMenu(wrapper) {
  await wrapper.find(".nameListMenuBtn").trigger("click");
  await flushPromises();
  return [...document.querySelectorAll(".nameListMenu > .v-list-item")];
}

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
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

  test("a list's row has one control, its menu", () => {
    const { wrapper } = mountBlock();
    const buttons = wrapper.find(".nameListRow").findAll("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0].classes()).toContain("nameListMenuBtn");
  });

  test("the menu opens, edits, copies, exports, renames and deletes", async () => {
    const { wrapper } = mountBlock();
    const items = await openRowMenu(wrapper);
    expect(items.map((item) => itemTitle(item))).toEqual([
      "Open",
      "Edit Issues",
      "Duplicate",
      "Export",
      "Rename",
      "Delete",
    ]);
  });

  test("rename and delete start from the menu", async () => {
    const { wrapper } = mountBlock();
    await clickMenuItem(wrapper, "Rename");
    expect(wrapper.find(".nameListEditField").exists()).toBe(true);
    wrapper.findComponent(NameListEditor).vm.cancelRename();
    await flushPromises();
    await clickMenuItem(wrapper, "Delete");
    expect(wrapper.findComponent(NameListEditor).vm.deleteTarget).toMatchObject(
      {
        pk: 2,
      },
    );
  });

  test("open routes to the list under the arcs collection", async () => {
    const { wrapper } = mountBlock();
    await clickMenuItem(wrapper, "Open");
    expect(useBrowserStore().routeWithSettings).toHaveBeenCalledWith(
      { topCollection: "arcs" },
      {
        name: "browser",
        params: { collection: "arcs", pks: "2", page: 1 },
      },
    );
  });

  test("an empty list's Open is off, and says why in words", async () => {
    // Opening an empty list bounced to the list of lists with no message.
    const lists = [
      { pk: 2, name: "Nothing Yet", personal: true, count: 0, editable: true },
    ];
    const { wrapper } = mountBlock({ lists });
    const items = await openRowMenu(wrapper);
    const open = items.find((item) => itemTitle(item) === "Open");
    expect(open.classList).toContain("v-list-item--disabled");
    expect(open.textContent).toContain("Add issues from any Reading Lists menu");
    open.click();
    await flushPromises();
    expect(useBrowserStore().routeWithSettings).not.toHaveBeenCalled();
  });

  test("edit opens the entry editor without admin powers", async () => {
    const { wrapper } = mountBlock();
    await clickMenuItem(wrapper, "Edit Issues");
    const dialog = wrapper.findComponent({ name: "ReviewDialog" });
    expect(dialog.exists()).toBe(true);
    expect(dialog.attributes("admin")).toBe("false");
    expect(wrapper.vm.showEditor).toBe(true);
  });

  test("a new list is made with the list name input", async () => {
    const { wrapper, store } = mountBlock();
    store.createList.mockResolvedValue({ pk: 3, name: "Next" });
    wrapper.vm.creating = true;
    await flushPromises();
    const input = wrapper.findComponent(ListNameInput);
    // Your own list names are taken; a global list's is not.
    expect(input.props("existingNames")).toEqual(["My Spidey"]);
    input.vm.$emit("submit", "Next");
    await flushPromises();
    expect(store.createList).toHaveBeenCalledWith("Next");
    expect(wrapper.vm.creating).toBe(false);
    expect(useBrowserStore().refreshBrowserPage).toHaveBeenCalledOnce();
  });

  test("a refused create keeps the input open with the server's reason", async () => {
    const { wrapper, store } = mountBlock();
    const reason = "You already have a reading list with that name.";
    store.createList.mockRejectedValue(
      new APIError(
        { status: "400", title: "Bad Request", detail: reason },
        400,
      ),
    );
    wrapper.vm.creating = true;
    await flushPromises();
    wrapper.findComponent(ListNameInput).vm.$emit("submit", "Next");
    await flushPromises();
    expect(wrapper.vm.creating).toBe(true);
    expect(wrapper.findComponent(ListNameInput).vm.shownError).toBe(reason);
  });

  test("anonymous sessions get nothing", () => {
    const { wrapper } = mountBlock({ loggedIn: false });
    expect(wrapper.find(".readingListsSettingsBlock").exists()).toBe(false);
  });
});
