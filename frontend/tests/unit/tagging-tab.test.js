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
 *     wrapper element, since Vuetify kills pointer events on disabled controls).
 *   - ``defaultSources`` order is run priority; enabling appends to the end,
 *     and per-row arrows reorder it. The section shows a hint explaining this.
 *   - A source with no stored credentials always reads as off, even if it
 *     lingers in ``defaultSources``.
 *   - Saving credentials for a source that had none enables it as a default
 *     source automatically; re-saving credentials leaves the checkbox alone.
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

  test("canMerge is true only with two or more enabled sources", () => {
    const oneEnabled = mountTab({
      hasMetronCredentials: true,
      hasComicvineCredentials: true,
      defaultSources: ["metron"],
    });
    expect(oneEnabled.vm.canMerge).toBe(false);

    const bothEnabled = mountTab({
      hasMetronCredentials: true,
      hasComicvineCredentials: true,
      defaultSources: ["metron", "comicvine"],
    });
    expect(bothEnabled.vm.canMerge).toBe(true);
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

  test("renders the priority-order hint paragraph", () => {
    expect(mountTab().find(".sourcesHint").exists()).toBe(true);
  });

  test("saving credentials for a new source enables it automatically", async () => {
    const wrapper = mountTab();
    const vm = wrapper.vm;
    const store = useAdminStore();
    // Simulate the server accepting the credentials and echoing back the model.
    store.updateTaggingDefaults.mockImplementation(() => {
      store.taggingDefaults = {
        ...store.taggingDefaults,
        hasMetronCredentials: true,
      };
    });

    vm.metronUser = "user";
    vm.metronPassword = "pass";
    await vm.saveMetronCredentials();
    await vm.$nextTick();
    expect(vm.draft.defaultSources).toContain("metron");
    expect(vm.metronEnabled).toBe(true);
    // The enable persists through the draft auto-save.
    expect(store.updateTaggingDefaults).toHaveBeenLastCalledWith(
      expect.objectContaining({
        defaultSources: expect.arrayContaining(["metron"]),
      }),
    );
  });

  test("re-saving credentials respects a deliberately disabled source", async () => {
    const wrapper = mountTab({ hasMetronCredentials: true });
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.metronUser = "user";
    vm.metronPassword = "pass";
    await vm.saveMetronCredentials();
    await vm.$nextTick();
    expect(vm.draft.defaultSources).not.toContain("metron");
    expect(vm.metronEnabled).toBe(false);
    // Only the credential save itself hit the server — no defaultSources write.
    expect(store.updateTaggingDefaults).toHaveBeenCalledTimes(1);
  });

  test("a failed credential save does not enable the source", async () => {
    const wrapper = mountTab();
    const vm = wrapper.vm;

    vm.metronUser = "user";
    // No password — the server would reject; defaults keep no credentials.
    await vm.saveMetronCredentials();
    await vm.$nextTick();
    expect(vm.draft.defaultSources).not.toContain("metron");
    expect(vm.metronEnabled).toBe(false);
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

describe("AdminTaggingTab — source priority order", () => {
  function mountBoth(defaultSources) {
    return mountTab({
      hasMetronCredentials: true,
      hasComicvineCredentials: true,
      defaultSources,
    });
  }

  test("enabling a source appends it at the end (lowest priority)", async () => {
    const vm = mountBoth(["comicvine"]).vm;
    vm.metronEnabled = true;
    await vm.$nextTick();
    // Appended after the existing comicvine, not prepended.
    expect(vm.draft.defaultSources).toEqual(["comicvine", "metron"]);
  });

  test("moveSource swaps adjacent entries and auto-saves", async () => {
    const wrapper = mountBoth(["metron", "comicvine"]);
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.moveSource("comicvine", -1);
    await vm.$nextTick();
    expect(vm.draft.defaultSources).toEqual(["comicvine", "metron"]);
    expect(store.updateTaggingDefaults).toHaveBeenLastCalledWith(
      expect.objectContaining({
        defaultSources: ["comicvine", "metron"],
      }),
    );
  });

  test("moveSource is a no-op at the priority boundaries", async () => {
    const vm = mountBoth(["metron", "comicvine"]).vm;
    vm.moveSource("metron", -1); // already first
    await vm.$nextTick();
    expect(vm.draft.defaultSources).toEqual(["metron", "comicvine"]);
    vm.moveSource("comicvine", 1); // already last
    await vm.$nextTick();
    expect(vm.draft.defaultSources).toEqual(["metron", "comicvine"]);
  });

  test("sourceRowStyle orders rows by priority, disabled sinks below", () => {
    const vm = mountBoth(["comicvine", "metron"]).vm;
    expect(vm.sourceRowStyle("comicvine")).toEqual({ order: 0 });
    expect(vm.sourceRowStyle("metron")).toEqual({ order: 1 });

    const off = mountTab({
      hasComicvineCredentials: true,
      defaultSources: ["comicvine"],
    }).vm;
    // Metron isn't in the priority list — it sinks below the enabled rows.
    expect(off.sourceRowStyle("metron")).toEqual({ order: 99 });
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

  test("toggling Merge all sources saves immediately", async () => {
    const wrapper = mountTab();
    const store = useAdminStore();

    wrapper.vm.draft.mergeAllSources = true;
    await wrapper.vm.$nextTick();
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith(
      expect.objectContaining({ mergeAllSources: true }),
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
