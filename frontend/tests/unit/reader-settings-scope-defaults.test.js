/*
 * The reader drawer's global scope compares against the admin's site
 * defaults: its override dot and its Clear button follow them, and fall back
 * to the factory JSON when ``/session`` delivered none.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import GLOBAL_DEFAULTS from "@/choices/reader-defaults.json";
import ReaderSettingsScope, {
  differsFromDefaults,
} from "@/components/reader/drawer/reader-settings-scope.vue";
import vuetify from "@/plugins/vuetify";

const SITE = Object.freeze({ ...GLOBAL_DEFAULTS, fitTo: "H" });

function mountScope({ globalSettings, defaults }) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { defaults },
      reader: { globalSettings },
    },
  });
  return mount(ReaderSettingsScope, { global: { plugins: [pinia, vuetify] } });
}

describe("differsFromDefaults", () => {
  test("falls back to the factory JSON", () => {
    expect(differsFromDefaults({ ...GLOBAL_DEFAULTS })).toBe(false);
    expect(differsFromDefaults({ ...GLOBAL_DEFAULTS, fitTo: "H" })).toBe(true);
  });

  test("compares against the given defaults", () => {
    expect(differsFromDefaults({ ...SITE }, SITE)).toBe(false);
    expect(differsFromDefaults({ ...GLOBAL_DEFAULTS }, SITE)).toBe(true);
  });
});

describe("ReaderSettingsScope — global scope", () => {
  test("settings at the site defaults show no dot and can't be cleared", () => {
    const wrapper = mountScope({
      globalSettings: { ...SITE },
      defaults: { reader: SITE },
    });
    expect(wrapper.vm.hasGlobalOverrides).toBe(false);
    expect(wrapper.vm.isGlobalClearDisabled).toBe(true);
  });

  test("factory settings differ from customized site defaults", () => {
    const wrapper = mountScope({
      globalSettings: { ...GLOBAL_DEFAULTS },
      defaults: { reader: SITE },
    });
    expect(wrapper.vm.hasGlobalOverrides).toBe(true);
    expect(wrapper.vm.isGlobalClearDisabled).toBe(false);
  });

  test("without site defaults the factory JSON decides", () => {
    const wrapper = mountScope({
      globalSettings: { ...GLOBAL_DEFAULTS },
      defaults: undefined,
    });
    expect(wrapper.vm.hasGlobalOverrides).toBe(false);
  });
});

export default {};
