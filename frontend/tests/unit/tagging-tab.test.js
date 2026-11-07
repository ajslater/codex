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
 *   - Metron is presented as an API key source like Comic Vine.
 *   - The Online Tagging Defaults section shows help for Match Mode and Prompts.
 *   - The Metadata Formats field's hint (not a section header) links out to the
 *     ComicInfo and MetronInfo docs.
 *   - Metadata Formats is a checkbox group whose last checked box is disabled
 *     and explained, so auto-save can never write an empty list. A row already
 *     saved empty shows an error and is not auto-saved on open.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import TaggingTab from "@/components/admin/tabs/tagging-tab.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
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
  metronKeySet: false,
  comicvineKeySet: false,
  comicvineUrl: "",
};

const SOURCE_TIP = "A source can only be enabled once its API key is saved.";

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

    vm.metronKey = "token";
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

    vm.metronKey = "token";
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

    // The server rejected the key; defaults keep no credentials.
    vm.metronKey = "bad";
    await vm.saveMetronCredentials();
    await vm.$nextTick();
    expect(vm.draft.defaultSources).not.toContain("metron");
    expect(vm.metronEnabled).toBe(false);
  });

  test("only Comic Vine offers a custom URL field", async () => {
    // simyan takes a base_url, so a Comic Vine proxy or mirror works. mokkari
    // hardcodes the metron.cloud endpoint, so Metron has no such field.
    const wrapper = mountTab({
      hasMetronCredentials: true,
      hasComicvineCredentials: true,
    });

    // The credential fields live in collapsed expansion panels, so expand
    // both before asserting — otherwise nothing is rendered to look at.
    for (const title of wrapper.findAll(".v-expansion-panel-title")) {
      await title.trigger("click");
    }
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(wrapper.text()).toContain("Save Metron Cloud API Key");
    expect(wrapper.text()).toContain("Save Comic Vine Credentials");
    // Metron's panel renders first, Comic Vine's second.
    const [metronPanel, comicvinePanel] = wrapper.findAll(".sourcePanel");
    expect(metronPanel.text()).not.toContain("Custom URL");
    expect(comicvinePanel.text()).toContain("Custom URL");
  });

  test("Metron reads as an API key source, like Comic Vine", async () => {
    const wrapper = mountTab({
      hasMetronCredentials: true,
      metronKeySet: true,
    });

    expect(wrapper.text()).toContain("API key set");
    // A saved key collapses the panel; open it to reach its Clear button.
    await wrapper.find(".v-expansion-panel-title").trigger("click");
    await new Promise((resolve) => setTimeout(resolve, 0));
    const [metronClear] = wrapper.findAllComponents(ConfirmDialog);
    expect(metronClear.props()).toMatchObject({
      buttonText: "Clear API Key",
      titleText: "Clear Metron Cloud API Key",
      text: "Remove the saved Metron Cloud API key?",
    });
  });

  test("saving sends only the API key, never a username or password", async () => {
    const wrapper = mountTab();
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.metronKey = "token";
    await vm.saveMetronCredentials();
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      metronKey: "token",
    });
    // The field is cleared so a saved key is never left sitting in the form.
    expect(vm.metronKey).toBe("");
  });

  test("clearing sends a blank key", async () => {
    const wrapper = mountTab({ hasMetronCredentials: true });
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.clearMetronCredentials();
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      metronKey: "",
    });
  });

  test("a custom URL saves on its own, without an API key", async () => {
    const wrapper = mountTab();
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.comicvineUrlLocal = "https://cv.example.com/api";
    await vm.saveComicvineCredentials();
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      comicvineUrl: "https://cv.example.com/api",
    });
    expect(vm.comicvineUrlLocal).toBe("");
    // A url is not a credential, so it must not enable the source.
    expect(vm.draft.defaultSources).not.toContain("comicvine");
  });

  test("clearing the Comic Vine key clears the custom URL too", () => {
    const wrapper = mountTab({ hasComicvineCredentials: true });
    const store = useAdminStore();

    wrapper.vm.clearComicvineCredentials();
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      comicvineKey: "",
      comicvineUrl: "",
    });
  });

  test("testing Comic Vine validates against the typed URL", async () => {
    const wrapper = mountTab({ hasComicvineCredentials: true });
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.comicvineUrlLocal = "https://cv.example.com/api";
    await vm.testComicvineCredentials();
    expect(store.validateTaggingCredentials).toHaveBeenCalledWith({
      source: "comicvine",
      comicvineUrl: "https://cv.example.com/api",
    });
  });

  test("a stored key can be tested without retyping it", () => {
    const vm = mountTab({ hasMetronCredentials: true, metronKeySet: true }).vm;
    expect(vm.canTestMetron).toBe(true);

    const unconfigured = mountTab().vm;
    expect(unconfigured.canTestMetron).toBe(false);
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

function mountBoth(defaultSources) {
  return mountTab({
    hasMetronCredentials: true,
    hasComicvineCredentials: true,
    defaultSources,
  });
}

describe("AdminTaggingTab — source priority order", () => {
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

function formatInput(wrapper, value) {
  return wrapper
    .findComponent({ name: "VCheckboxGroup" })
    .find(`input[value="${value}"]`);
}

describe("AdminTaggingTab — Metadata Formats checkboxes", () => {
  test("the last checked format is disabled and explained", () => {
    const wrapper = mountTab({ defaultFormats: ["COMIC_INFO"] });
    expect(wrapper.findComponent({ name: "VCheckboxGroup" }).exists()).toBe(
      true,
    );
    expect(formatInput(wrapper, "COMIC_INFO").element.disabled).toBe(true);
    expect(formatInput(wrapper, "METRON_INFO").element.disabled).toBe(false);
    expect(wrapper.text()).toContain("At least one format must be written");
  });

  test("checking a second format enables both and auto-saves", async () => {
    const wrapper = mountTab({ defaultFormats: ["COMIC_INFO"] });
    const store = useAdminStore();
    await formatInput(wrapper, "METRON_INFO").setValue(true);
    expect(wrapper.vm.draft.defaultFormats).toEqual([
      "COMIC_INFO",
      "METRON_INFO",
    ]);
    expect(formatInput(wrapper, "COMIC_INFO").element.disabled).toBe(false);
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith(
      expect.objectContaining({
        defaultFormats: ["COMIC_INFO", "METRON_INFO"],
      }),
    );
  });

  test("an empty saved row shows an error and does not auto-save", async () => {
    const wrapper = mountTab({ defaultFormats: [] });
    const store = useAdminStore();
    await wrapper.vm.$nextTick();
    const errors = wrapper.findAll(".v-messages__message").map((m) => m.text());
    expect(errors).toContain("Choose at least one format");
    expect(formatInput(wrapper, "COMIC_INFO").element.disabled).toBe(false);
    expect(store.updateTaggingDefaults).not.toHaveBeenCalled();
  });
});

export default {};
