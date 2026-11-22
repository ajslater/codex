/*
 * The list name limit comes from the server's limits, not a copy.
 *
 * ``limits.json`` is mocked to a length no hardcoded copy would match, so
 * the create input and the rename field both have to read it.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

vi.mock(import("@/choices/limits.json"), async (importOriginal) => {
  const original = await importOriginal();
  return { default: { ...original.default, maxNameLen: 12 } };
});

import BrowserSettingsReadingLists from "@/components/browser/drawer/browser-settings-reading-lists.vue";
import ListNameInput from "@/components/list-name-input.vue";
import NameListEditor from "@/components/name-list-editor.vue";
import vuetify from "@/plugins/vuetify";

describe("list name max length", () => {
  test("the name input takes the server's limit", async () => {
    const wrapper = mount(ListNameInput, {
      global: { plugins: [vuetify] },
      props: { autofocus: false },
    });
    const input = wrapper.find('input[role="combobox"]');
    expect(input.attributes("maxlength")).toBe("12");
    wrapper.vm.name = "x".repeat(13);
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.isValid).toBe(false);
  });

  test("the rename field takes it too", () => {
    const pinia = createTestingPinia({
      initialState: {
        auth: { user: { id: 1 } },
        readingLists: { myLists: [], myListsLoaded: true },
      },
    });
    const wrapper = mount(BrowserSettingsReadingLists, {
      global: { plugins: [pinia, vuetify], stubs: { ReviewDialog: true } },
    });
    expect(wrapper.findComponent(NameListEditor).props("maxLength")).toBe(12);
  });
});
