/*
 * The settings drawer's "Shelves" block (``browser-settings-shelves.vue``)
 * and the generic ``name-list-editor.vue`` it renders its list with:
 * shelves listed with their item counts, inline rename, delete behind a
 * confirmation, "New shelf", and nothing at all for anonymous sessions.
 * Real Vuetify is mounted; store actions are stubbed by
 * createTestingPinia so calls can be asserted.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test } from "vitest";

import BrowserSettingsShelves from "@/components/browser/drawer/browser-settings-shelves.vue";
import NameListEditor from "@/components/name-list-editor.vue";
import ShelfNameInput from "@/components/shelf-name-input.vue";
import vuetify from "@/plugins/vuetify";
import { useShelvesStore } from "@/stores/shelves";

beforeAll(() => {
  /*
   * VOverlay's connected location strategy reads the bare global; happy-dom
   * has no visual viewport, so the name combobox's menu never positions
   * without this.
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

const SHELVES = () => [
  shelf(1, "Favorites", { series: [1, 2], comics: [42] }),
  shelf(2, "Want to Read", { comics: [7] }),
];

const wrappers = [];

function mountBlock({ loggedIn = true, shelves = SHELVES() } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: loggedIn ? { pk: 1 } : null },
      shelves: { shelves, hydrated: true },
    },
    stubActions: true,
  });
  const wrapper = mount(BrowserSettingsShelves, {
    attachTo: document.body,
    global: { plugins: [pinia, vuetify] },
  });
  wrappers.push(wrapper);
  return { wrapper, shelvesStore: useShelvesStore() };
}

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
});

describe("BrowserSettingsShelves", () => {
  test("lists each shelf with its item count", () => {
    const { wrapper } = mountBlock();
    expect(wrapper.find(".settingsSubHeader").text()).toBe("Shelves");
    const rows = wrapper.findAll(".nameListRow");
    expect(rows.map((row) => row.find(".v-list-item-title").text())).toEqual([
      "Favorites",
      "Want to Read",
    ]);
    expect(rows.map((row) => row.find(".v-list-item-subtitle").text())).toEqual(
      ["3 items", "1 item"],
    );
  });

  test("renders nothing for anonymous sessions", () => {
    const { wrapper } = mountBlock({ loggedIn: false });
    expect(wrapper.find(".shelvesSettingsBlock").exists()).toBe(false);
    expect(wrapper.findComponent(NameListEditor).exists()).toBe(false);
  });

  test("says so when there are no shelves", () => {
    const { wrapper } = mountBlock({ shelves: [] });
    expect(wrapper.find(".nameListEmpty").text()).toBe("No shelves yet");
  });

  test("renaming inline calls renameShelf", async () => {
    const { wrapper, shelvesStore } = mountBlock();
    await wrapper.findAll(".nameListRenameBtn")[0].trigger("click");

    const field = wrapper.find(".nameListEditField input");
    expect(field.element.value).toBe("Favorites");
    await field.setValue("  Best Of ");
    await wrapper.find(".nameListSaveBtn").trigger("click");

    expect(shelvesStore.renameShelf).toHaveBeenCalledExactlyOnceWith(
      1,
      "Best Of",
    );
    expect(wrapper.find(".nameListEditField").exists()).toBe(false);
  });

  test("a rename to another shelf's name is refused", async () => {
    const { wrapper, shelvesStore } = mountBlock();
    await wrapper.findAll(".nameListRenameBtn")[0].trigger("click");
    await wrapper.find(".nameListEditField input").setValue("Want to Read");

    expect(
      wrapper.find(".nameListSaveBtn").attributes("disabled"),
    ).toBeDefined();
    await wrapper.find(".nameListEditField input").trigger("keydown.enter");
    expect(shelvesStore.renameShelf).not.toHaveBeenCalled();
  });

  test("an unchanged name or a cancel sends nothing", async () => {
    const { wrapper, shelvesStore } = mountBlock();
    await wrapper.findAll(".nameListRenameBtn")[0].trigger("click");
    await wrapper.find(".nameListSaveBtn").trigger("click");
    await wrapper.findAll(".nameListRenameBtn")[1].trigger("click");
    await wrapper.find(".nameListCancelBtn").trigger("click");
    expect(shelvesStore.renameShelf).not.toHaveBeenCalled();
  });

  test("delete asks first, then calls deleteShelf", async () => {
    const { wrapper, shelvesStore } = mountBlock();
    await wrapper.findAll(".nameListDeleteBtn")[1].trigger("click");
    await flushPromises();

    const dialog = document.querySelector(".confirmDialog");
    expect(dialog.textContent).toContain('Delete the shelf "Want to Read"?');
    expect(shelvesStore.deleteShelf).not.toHaveBeenCalled();

    dialog.querySelector(".confirmButton").click();
    await flushPromises();
    expect(shelvesStore.deleteShelf).toHaveBeenCalledExactlyOnceWith(2);
  });

  test("cancelling the confirmation deletes nothing", async () => {
    const { wrapper, shelvesStore } = mountBlock();
    await wrapper.findAll(".nameListDeleteBtn")[0].trigger("click");
    await flushPromises();

    document.querySelector(".confirmDialog .cancelButton").click();
    await flushPromises();

    expect(shelvesStore.deleteShelf).not.toHaveBeenCalled();
    expect(wrapper.findComponent(NameListEditor).vm.deleteTarget).toBeNull();
  });

  test("New shelf reveals the name input and creates the shelf", async () => {
    const { wrapper, shelvesStore } = mountBlock();
    shelvesStore.createShelf.mockResolvedValue(shelf(9, "Finished"));
    await wrapper.find(".shelvesSettingsNewBtn").trigger("click");

    const input = wrapper.findComponent(ShelfNameInput);
    expect(input.vm.suggestions).toEqual(["Reading Now", "Finished"]);
    input.vm.$emit("submit", "Finished");
    await flushPromises();

    expect(shelvesStore.createShelf).toHaveBeenCalledExactlyOnceWith(
      "Finished",
    );
    expect(wrapper.findComponent(ShelfNameInput).exists()).toBe(false);
  });
});

describe("NameListEditor", () => {
  test("labels follow the noun and counts are optional", () => {
    const wrapper = mount(NameListEditor, {
      global: { plugins: [vuetify] },
      props: {
        items: [{ pk: 5, name: "Summer" }],
        noun: "reading list",
      },
    });
    wrappers.push(wrapper);
    expect(wrapper.find(".nameListRenameBtn").attributes("title")).toBe(
      "Rename reading list",
    );
    expect(wrapper.find(".nameListDeleteBtn").attributes("title")).toBe(
      "Delete reading list",
    );
    expect(wrapper.find(".v-list-item-subtitle").exists()).toBe(false);
  });
});
