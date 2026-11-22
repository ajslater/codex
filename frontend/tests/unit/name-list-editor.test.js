/*
 * ``name-list-editor.vue``, the drawer's list of named things to rename
 * and delete in place. Kept from the shelves drawer tests when shelves
 * folded into reading lists: inline rename that refuses a taken name and
 * sends nothing for an unchanged one, delete behind a confirmation, and
 * Enter mid IME composition renaming nothing. Real Vuetify is mounted.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test } from "vitest";

import NameListEditor from "@/components/name-list-editor.vue";
import vuetify from "@/plugins/vuetify";

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

const ITEMS = Object.freeze([
  { pk: 1, name: "Favorites", count: 3 },
  { pk: 2, name: "Want to Read", count: 1 },
]);

const wrappers = [];

function mountEditor(props = {}) {
  const wrapper = mount(NameListEditor, {
    attachTo: document.body,
    global: { plugins: [vuetify] },
    props: {
      items: ITEMS,
      noun: "reading list",
      countNoun: "issue",
      ...props,
    },
  });
  wrappers.push(wrapper);
  return wrapper;
}

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
});

describe("NameListEditor", () => {
  test("lists each name with its count; labels follow the noun", () => {
    const wrapper = mountEditor();
    expect(wrapper.text()).toContain("3 issues");
    expect(wrapper.text()).toContain("1 issue");
    expect(wrapper.find(".nameListRenameBtn").attributes("title")).toBe(
      "Rename reading list",
    );
    expect(wrapper.find(".nameListDeleteBtn").attributes("title")).toBe(
      "Delete reading list",
    );
  });

  test("counts are optional", () => {
    const wrapper = mountEditor({ items: [{ pk: 5, name: "Summer" }] });
    expect(wrapper.find(".v-list-item-subtitle").exists()).toBe(false);
  });

  test("says so when there is nothing", () => {
    const wrapper = mountEditor({ items: [], emptyText: "None yet" });
    expect(wrapper.text()).toContain("None yet");
  });

  test("renaming inline emits the trimmed name", async () => {
    const wrapper = mountEditor();
    await wrapper.findAll(".nameListRenameBtn")[0].trigger("click");
    const field = wrapper.find(".nameListEditField input");
    expect(field.element.value).toBe("Favorites");
    await field.setValue("  Best Of ");
    await wrapper.find(".nameListSaveBtn").trigger("click");
    expect(wrapper.emitted("rename")).toEqual([[{ pk: 1, name: "Best Of" }]]);
    expect(wrapper.find(".nameListEditField").exists()).toBe(false);
  });

  test("a rename to another item's name is refused", async () => {
    const wrapper = mountEditor();
    await wrapper.findAll(".nameListRenameBtn")[0].trigger("click");
    await wrapper.find(".nameListEditField input").setValue("Want to Read");
    expect(
      wrapper.find(".nameListSaveBtn").attributes("disabled"),
    ).toBeDefined();
    await wrapper.find(".nameListEditField input").trigger("keydown.enter");
    expect(wrapper.emitted("rename")).toBeUndefined();
  });

  test("an unchanged name or a cancel sends nothing", async () => {
    const wrapper = mountEditor();
    await wrapper.findAll(".nameListRenameBtn")[0].trigger("click");
    await wrapper.find(".nameListSaveBtn").trigger("click");
    await wrapper.findAll(".nameListRenameBtn")[1].trigger("click");
    await wrapper.find(".nameListCancelBtn").trigger("click");
    expect(wrapper.emitted("rename")).toBeUndefined();
  });

  test("delete asks first, then emits", async () => {
    const wrapper = mountEditor({ deleteHint: "No comic file changes." });
    await wrapper.findAll(".nameListDeleteBtn")[1].trigger("click");
    await flushPromises();
    const dialog = document.querySelector(".confirmDialog");
    expect(dialog.textContent).toContain(
      'Delete the reading list "Want to Read"? No comic file changes.',
    );
    expect(wrapper.emitted("delete")).toBeUndefined();
    dialog.querySelector(".confirmButton").click();
    await flushPromises();
    expect(wrapper.emitted("delete")).toEqual([[2]]);
  });

  test("cancelling the confirmation deletes nothing", async () => {
    const wrapper = mountEditor();
    await wrapper.findAll(".nameListDeleteBtn")[0].trigger("click");
    await flushPromises();
    document.querySelector(".confirmDialog .cancelButton").click();
    await flushPromises();
    expect(wrapper.emitted("delete")).toBeUndefined();
    expect(wrapper.vm.deleteTarget).toBeNull();
  });

  test("Enter while an IME composes renames nothing", async () => {
    const wrapper = mountEditor();
    await wrapper.findAll(".nameListRenameBtn")[0].trigger("click");
    const field = wrapper.find(".nameListEditField input");
    await field.setValue("Best Of");
    await field.trigger("keydown", { key: "Enter", isComposing: true });
    await field.trigger("keydown", { key: "Enter", keyCode: 229 });
    expect(wrapper.emitted("rename")).toBeUndefined();
    await field.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("rename")).toEqual([[{ pk: 1, name: "Best Of" }]]);
  });
});
