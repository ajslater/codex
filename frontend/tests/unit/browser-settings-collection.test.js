/*
 * The browser drawer's Show Collection Levels checkboxes.
 *
 * Behavior locked in here:
 *   - The levels are one VCheckboxGroup labelled by the drawer sub-header.
 *   - A click sends exactly one setSettings call carrying only the flag it
 *     flipped, since every settings change reloads the browser page.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import BrowserSettingsCollection from "@/components/browser/drawer/browser-settings-collection.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

function mountSettings() {
  const pinia = createTestingPinia({
    initialState: {
      // The store's own static choices supply the four levels.
      browser: {
        settings: {
          show: {
            publishers: true,
            imprints: true,
            series: true,
            volumes: false,
          },
        },
      },
    },
  });
  const wrapper = mount(BrowserSettingsCollection, {
    global: {
      plugins: [pinia, vuetify],
      mocks: { $route: { params: { collection: "publishers" } } },
    },
  });
  return { wrapper, store: useBrowserStore() };
}

describe("BrowserSettingsCollection", () => {
  test("renders the levels as a labelled checkbox group", () => {
    const { wrapper } = mountSettings();
    const group = wrapper.findComponent({ name: "VCheckboxGroup" });
    expect(group.exists()).toBe(true);
    expect(group.find(".v-label .settingsSubHeader").text()).toBe(
      "Show Collection Levels",
    );
    expect(group.find('input[value="imprints"]').element.checked).toBe(true);
    expect(group.find('input[value="volumes"]').element.checked).toBe(false);
  });

  test("unchecking Imprints sends only the imprints flag", async () => {
    const { wrapper, store } = mountSettings();
    await wrapper.find('input[value="imprints"]').setValue(false);
    expect(store.setSettings).toHaveBeenCalledTimes(1);
    expect(store.setSettings).toHaveBeenCalledWith({
      show: { imprints: false },
    });
  });

  test("checking Volumes sends only the volumes flag", async () => {
    const { wrapper, store } = mountSettings();
    await wrapper.find('input[value="volumes"]').setValue(true);
    expect(store.setSettings).toHaveBeenCalledTimes(1);
    expect(store.setSettings).toHaveBeenCalledWith({
      show: { volumes: true },
    });
  });
});

export default {};
