/*
 * Tests for the Admin Tagging tab's auto-save, section layout, Online Sources
 * controls, and Write Defaults help text.
 *
 * Behavior locked in here:
 *   - The Tagging Defaults and Online Tagging Defaults sections auto-save the
 *     moment a field changes; there is no Save Defaults / Revert button.
 *   - The sections render in order: Tagging Defaults, Online Tagging Defaults,
 *     Online Tagging Sources.
 *   - The Online Sources combo box is gone; each source is enabled by a
 *     checkbox to the left of its credential panel.
 *   - That checkbox drives ``draft.defaultSources``, which auto-saves the moment
 *     it changes, and is disabled until the source's credentials exist.
 *   - A disabled source checkbox explains itself with a title tooltip (on a
 *     wrapper element, since Vuetify kills pointer events on disabled controls);
 *     there is no longer an inline sources hint paragraph.
 *   - A source with no stored credentials always reads as off, even if it
 *     lingers in ``defaultSources``.
 *   - The Online Tagging Defaults section shows help for Match Mode and Prompts.
 *   - The Metadata Formats field's hint (not a section header) links out to the
 *     ComicInfo and MetronInfo docs.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import TaggingTab from "@/components/admin/tabs/tagging-tab.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";

const BASE_DEFAULTS = {
  defaultFormats: ["COMIC_INFO"],
  deleteOriginal: false,
  defaultMatchMode: "auto",
  defaultPromptsMode: "ask",
  defaultSources: [],
  hasMetronCredentials: false,
  hasComicvineCredentials: false,
  metronUserSet: false,
  metronPasswordSet: false,
  metronUrl: "",
  comicvineKeySet: false,
  comicvineUrl: "",
};

const SOURCE_TIP =
  "A source can only be enabled once its credentials are saved.";

function mountTab(overrides = {}) {
  const taggingDefaults = { ...BASE_DEFAULTS, ...overrides };
  const pinia = createTestingPinia({
    initialState: { admin: { taggingDefaults } },
  });
  return mount(TaggingTab, {
    global: {
      plugins: [pinia, vuetify],
      stubs: {
        TagWriteErrorsPanel: true,
        ValidationChip: true,
        ConfirmDialog: true,
      },
    },
  });
}

describe("AdminTaggingTab — Online Sources enable checkboxes", () => {
  test("metronEnabled reflects and auto-saves draft.defaultSources", async () => {
    const wrapper = mountTab({ hasMetronCredentials: true });
    const vm = wrapper.vm;
    const store = useAdminStore();
    expect(vm.metronEnabled).toBe(false);
    expect(store.updateTaggingDefaults).not.toHaveBeenCalled();

    vm.metronEnabled = true;
    await vm.$nextTick();
    expect(vm.draft.defaultSources).toContain("metron");
    expect(vm.metronEnabled).toBe(true);
    // Toggling a source persists immediately — no Save button required.
    expect(store.updateTaggingDefaults).toHaveBeenCalled();

    vm.metronEnabled = false;
    await vm.$nextTick();
    expect(vm.draft.defaultSources).not.toContain("metron");
  });

  test("a credential-less source reads as off even if listed in defaultSources", () => {
    const wrapper = mountTab({
      hasMetronCredentials: false,
      defaultSources: ["metron"],
    });
    expect(wrapper.vm.metronEnabled).toBe(false);
  });

  test("the enable checkbox is disabled until credentials exist", () => {
    const off = mountTab({ hasMetronCredentials: false });
    const offInput = off.findAll(".sourceEnable")[0].find("input");
    expect(offInput.element.disabled).toBe(true);

    const on = mountTab({ hasMetronCredentials: true });
    const onInput = on.findAll(".sourceEnable")[0].find("input");
    expect(onInput.element.disabled).toBe(false);
  });

  test("a disabled source checkbox explains itself with a title tooltip", () => {
    // The title sits on the wrapper, not the checkbox, because Vuetify sets
    // pointer-events:none on disabled controls (see edit-panel tooltips).
    const off = mountTab({ hasMetronCredentials: false });
    expect(off.findAll(".sourceEnable")[0].attributes("title")).toBe(
      SOURCE_TIP,
    );

    const on = mountTab({ hasMetronCredentials: true });
    expect(on.findAll(".sourceEnable")[0].attributes("title")).toBe("");
  });

  test("no longer renders the inline sources hint paragraph", () => {
    expect(mountTab().find(".sourcesHint").exists()).toBe(false);
  });

  test("toggling one source leaves the other untouched", async () => {
    const wrapper = mountTab({
      hasMetronCredentials: true,
      hasComicvineCredentials: true,
      defaultSources: ["comicvine"],
    });
    const vm = wrapper.vm;
    expect(vm.comicvineEnabled).toBe(true);

    vm.metronEnabled = true;
    await vm.$nextTick();
    expect(vm.draft.defaultSources).toEqual(
      expect.arrayContaining(["comicvine", "metron"]),
    );
    expect(vm.comicvineEnabled).toBe(true);
  });
});

describe("AdminTaggingTab — auto-save & layout", () => {
  test("editing a Tagging Defaults field saves immediately", async () => {
    const wrapper = mountTab();
    const store = useAdminStore();
    expect(store.updateTaggingDefaults).not.toHaveBeenCalled();

    wrapper.vm.draft.deleteOriginal = true;
    await wrapper.vm.$nextTick();
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith(
      expect.objectContaining({ deleteOriginal: true }),
    );
  });

  test("editing an Online Tagging Defaults field saves immediately", async () => {
    const wrapper = mountTab();
    const store = useAdminStore();

    wrapper.vm.draft.defaultMatchMode = "eager";
    await wrapper.vm.$nextTick();
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith(
      expect.objectContaining({ defaultMatchMode: "eager" }),
    );
  });

  test("renders no Save Defaults or Revert buttons", () => {
    const text = mountTab().text();
    expect(text).not.toContain("Save Defaults");
    expect(text).not.toContain("Revert");
  });

  test("orders Online Tagging Defaults before Online Tagging Sources", () => {
    const headings = mountTab()
      .findAll("h3")
      .map((h) => h.text());
    expect(headings).toEqual([
      "Tagging Defaults",
      "Online Tagging Defaults",
      "Online Tagging Sources",
    ]);
  });
});

describe("AdminTaggingTab — Online Tagging Defaults help", () => {
  test("explains Match Mode and Prompts", () => {
    const text = mountTab().text();
    expect(text).toContain("How aggressively to accept online matches");
    expect(text).toContain("What to do with matches that are too ambiguous");
  });
});

describe("AdminTaggingTab — Metadata Formats hint", () => {
  test("renders the ComicInfo and MetronInfo docs links inside the field hint", () => {
    const wrapper = mountTab();
    // The links live inside the field's own hint message, not a section header.
    const hint = wrapper
      .findAll(".v-messages__message")
      .find((m) => m.text().includes("These metadata formats"));
    expect(hint).toBeTruthy();
    const hrefs = hint.findAll("a").map((a) => a.attributes("href"));
    expect(hrefs).toContain(
      "https://anansi-project.github.io/docs/category/comicinfo",
    );
    expect(hrefs).toContain(
      "https://metron-project.github.io/docs/category/metroninfo",
    );
  });
});

export default {};
