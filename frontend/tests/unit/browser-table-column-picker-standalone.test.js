/*
 * The column picker's standalone mode, used by the admin Defaults tab.
 *
 * Standalone reads its collection, columns and show flags from props, emits
 * ``save`` with the list, and never touches the browser store. Live mode,
 * mounted in the same file, still reads the store and falls back to the
 * admin's site default before the registry.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import BROWSER_TABLE_DEFAULT_COLUMNS from "@/choices/browser-table-default-columns.json";
import BrowserTableColumnPicker from "@/components/browser/table/browser-table-column-picker.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

const SHOW = Object.freeze({
  publishers: true,
  imprints: false,
  series: true,
  volumes: false,
});

function mountPicker(props, { settings = {}, defaults } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { defaults },
      browser: {
        settings: {
          topCollection: "comics",
          tableColumns: {},
          show: SHOW,
          ...settings,
        },
      },
    },
  });
  const wrapper = mount(BrowserTableColumnPicker, {
    props: { modelValue: false, ...props },
    global: { plugins: [pinia, vuetify], stubs: { VDialog: true } },
  });
  return { wrapper, vm: wrapper.vm, store: useBrowserStore() };
}

async function open(wrapper) {
  await wrapper.setProps({ modelValue: true });
}

describe("column picker — standalone", () => {
  test("reads its props, not the store", async () => {
    const { wrapper, vm } = mountPicker({
      standalone: true,
      standaloneTopCollection: "folders",
      standaloneColumns: ["cover", "size"],
      standaloneShow: SHOW,
    });
    await open(wrapper);
    expect(vm.topCollection).toBe("folders");
    expect(vm.draft).toEqual(["cover", "size"]);
  });

  test("an empty list starts from the registry default", async () => {
    const { wrapper, vm } = mountPicker(
      {
        standalone: true,
        standaloneTopCollection: "folders",
        standaloneColumns: [],
        standaloneShow: SHOW,
      },
      { defaults: { browser: { tableColumns: { folders: ["name"] } } } },
    );
    await open(wrapper);
    expect(vm.draft).toEqual(BROWSER_TABLE_DEFAULT_COLUMNS.folders);
  });

  test("Save emits the list and never saves settings", async () => {
    const { wrapper, vm, store } = mountPicker({
      standalone: true,
      standaloneTopCollection: "folders",
      standaloneColumns: ["cover", "size"],
      standaloneShow: SHOW,
    });
    await open(wrapper);
    vm.removeColumn("size");
    vm.onSave();
    expect(wrapper.emitted("save")).toEqual([[["cover"]]]);
    expect(wrapper.emitted("update:modelValue")).toEqual([[false]]);
    expect(store.setSettings).not.toHaveBeenCalled();
  });

  test("an empty Save emits an empty list, which the tab reads as factory", async () => {
    const { wrapper, vm } = mountPicker({
      standalone: true,
      standaloneTopCollection: "folders",
      standaloneColumns: ["cover"],
      standaloneShow: SHOW,
    });
    await open(wrapper);
    vm.selectNone();
    vm.onSave();
    expect(wrapper.emitted("save")).toEqual([[[]]]);
  });

  test("Defaults means the registry", async () => {
    const { wrapper, vm } = mountPicker(
      {
        standalone: true,
        standaloneTopCollection: "folders",
        standaloneColumns: ["size"],
        standaloneShow: SHOW,
      },
      { defaults: { browser: { tableColumns: { folders: ["name"] } } } },
    );
    await open(wrapper);
    vm.resetToDefaults();
    expect(vm.draft).toEqual(BROWSER_TABLE_DEFAULT_COLUMNS.folders);
  });
});

describe("column picker — live", () => {
  test("reads the store and falls back to the site default", async () => {
    const { wrapper, vm } = mountPicker(
      {},
      {
        defaults: { browser: { tableColumns: { comics: ["cover", "name"] } } },
      },
    );
    await open(wrapper);
    expect(vm.topCollection).toBe("comics");
    expect(vm.draft).toEqual(["cover", "name"]);
  });

  test("the visitor's own columns win and Save goes to the store", async () => {
    const { wrapper, vm, store } = mountPicker(
      {},
      {
        settings: { tableColumns: { comics: ["size"] } },
        defaults: { browser: { tableColumns: { comics: ["cover", "name"] } } },
      },
    );
    await open(wrapper);
    expect(vm.draft).toEqual(["size"]);
    vm.onSave();
    expect(store.setSettings).toHaveBeenCalledWith({
      tableColumns: { comics: ["size"] },
    });
    expect(wrapper.emitted("save")).toBeUndefined();
  });
});

export default {};
