/*
 * Picking a saved view from the settings drawer's "Load Saved View" menu.
 *
 * Loading the view changes the browser settings, which clears the
 * combobox. Vuetify re-opens a focused combobox's menu when its model
 * changes, so the menu popped back open after every pick.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test, vi } from "vitest";
import { VCombobox } from "vuetify/components";

vi.mock("@/plugins/router", () => ({
  default: { currentRoute: { value: { params: {}, query: {} } } },
}));
vi.mock("@/api/v4/browser", () => ({ getSavedSettingsList: vi.fn() }));

import BrowserSettingsSaved from "@/components/browser/drawer/browser-settings-saved.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

const SAVED = [
  { pk: 3, name: "Added Recently" },
  { pk: 7, name: "DC by Year" },
];

describe("picking a saved view", () => {
  let wrapper;

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

  afterEach(() => {
    wrapper?.unmount();
    document.body.replaceChildren();
  });

  const openMenu = async () => {
    const pinia = createTestingPinia({
      initialState: { browser: { savedSettingsList: SAVED } },
    });
    wrapper = mount(BrowserSettingsSaved, {
      attachTo: document.body,
      global: { plugins: [vuetify, pinia] },
    });
    wrapper.find("input").element.focus();
    await wrapper.find(".v-field").trigger("mousedown");
    await flushPromises();
    return {
      combobox: wrapper.findComponent(VCombobox),
      store: useBrowserStore(pinia),
    };
  };

  const pickView = async (name) => {
    const opened = await openMenu();
    const option = [...document.querySelectorAll('[role="option"]')].find(
      (el) => el.textContent.trim() === name,
    );
    option.click();
    await flushPromises();
    return opened;
  };

  test("the menu stays closed when the view's settings land", async () => {
    const { combobox, store } = await pickView("DC by Year");
    expect(store.loadSavedSettings).toHaveBeenCalledWith(7);
    expect(combobox.vm.menu).toBe(false);

    // What loadSavedSettings does once the view arrives.
    store.settings.orderBy = "date";
    await flushPromises();

    expect(combobox.vm.menu).toBe(false);
  });

  test("the loaded view's name is cleared", async () => {
    const { combobox, store } = await pickView("DC by Year");
    expect(combobox.vm.search).toBe("DC by Year");

    store.settings.orderBy = "date";
    await flushPromises();

    expect(combobox.props("modelValue")).toBeNull();
    expect(combobox.vm.search).toBe("");
  });

  test("a page load doesn't close a menu opened after it started", async () => {
    const { combobox, store } = await openMenu();
    expect(combobox.vm.menu).toBe(true);

    // loadBrowserPage re-sets the breadcrumbs on every response.
    store.settings.breadcrumbs = [];
    await flushPromises();

    expect(combobox.vm.menu).toBe(true);
    expect(combobox.vm.isFocused).toBe(true);
  });
});

export default {};
