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
 *   - One row per source the backend lists, in its order, Metron then Comic
 *     Vine; each row's copy comes from the source's descriptor.
 *   - That checkbox drives ``draft.defaultSources``, which auto-saves the moment
 *     it changes, and is disabled until the source is in the server's
 *     ``configuredSources``.
 *   - A disabled source checkbox explains itself with a title tooltip (on a
 *     wrapper element, since Vuetify kills pointer events on disabled controls).
 *   - ``defaultSources`` order is priority (run order, and the merge winner
 *     where sources disagree); enabling appends to the end, and per-row
 *     arrows reorder it. The section shows a hint explaining this.
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
 *   - comicbox's keep is offered there with a hint saying what it rewrites and
 *     refuses. It never counts as the format a write must name, so it is
 *     disabled while no format is checked.
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
  configuredSources: [],
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
  test("the enable checkbox reflects and auto-saves draft.defaultSources", async () => {
    const wrapper = mountTab({ configuredSources: ["metron"] });
    const vm = wrapper.vm;
    const store = useAdminStore();
    const metronInput = () => wrapper.findAll(".sourceEnable")[0].find("input");
    expect(vm.isSourceEnabled("metron")).toBe(false);
    expect(store.updateTaggingDefaults).not.toHaveBeenCalled();

    await metronInput().setValue(true);
    expect(vm.draft.defaultSources).toContain("metron");
    expect(vm.isSourceEnabled("metron")).toBe(true);
    expect(metronInput().element.checked).toBe(true);
    // Toggling a source persists immediately — no Save button required.
    expect(store.updateTaggingDefaults).toHaveBeenCalled();

    await metronInput().setValue(false);
    expect(vm.draft.defaultSources).not.toContain("metron");
  });

  test("a credential-less source reads as off even if listed in defaultSources", () => {
    const wrapper = mountTab({
      configuredSources: [],
      defaultSources: ["metron"],
    });
    expect(wrapper.vm.isSourceEnabled("metron")).toBe(false);
  });

  test("canMerge is true only with two or more enabled sources", () => {
    const oneEnabled = mountTab({
      configuredSources: ["metron", "comicvine"],
      defaultSources: ["metron"],
    });
    expect(oneEnabled.vm.canMerge).toBe(false);

    const bothEnabled = mountTab({
      configuredSources: ["metron", "comicvine"],
      defaultSources: ["metron", "comicvine"],
    });
    expect(bothEnabled.vm.canMerge).toBe(true);
  });

  test("the enable checkbox is disabled until credentials exist", () => {
    const off = mountTab({ configuredSources: [] });
    const offInput = off.findAll(".sourceEnable")[0].find("input");
    expect(offInput.element.disabled).toBe(true);

    const on = mountTab({ configuredSources: ["metron"] });
    const onInput = on.findAll(".sourceEnable")[0].find("input");
    expect(onInput.element.disabled).toBe(false);
  });

  test("a disabled source checkbox explains itself with a title tooltip", () => {
    // The title sits on the wrapper, not the checkbox, because Vuetify sets
    // pointer-events:none on disabled controls (see edit-panel tooltips).
    const off = mountTab({ configuredSources: [] });
    expect(off.findAll(".sourceEnable")[0].attributes("title")).toBe(
      SOURCE_TIP,
    );

    const on = mountTab({ configuredSources: ["metron"] });
    expect(on.findAll(".sourceEnable")[0].attributes("title")).toBe("");
  });

  test("renders the priority-order hint paragraph", () => {
    expect(mountTab().find(".sourcesHint").exists()).toBe(true);
  });

  test("the priority hint says the list order is the precedence order", () => {
    const hint = mountTab().find(".sourcesHint").text();
    expect(hint).toContain(
      "The enabled sources below are listed in priority order, highest first",
    );
    expect(hint).toContain(
      "where they disagree, the source higher in the list wins.",
    );
  });

  test("saving credentials for a new source enables it automatically", async () => {
    const wrapper = mountTab();
    const vm = wrapper.vm;
    const store = useAdminStore();
    // Simulate the server accepting the credentials and echoing back the model.
    store.updateTaggingDefaults.mockImplementation(() => {
      store.taggingDefaults = {
        ...store.taggingDefaults,
        configuredSources: ["metron"],
      };
    });

    vm.keys.metron = "token";
    await vm.saveCredentials("metron");
    await vm.$nextTick();
    expect(vm.draft.defaultSources).toContain("metron");
    expect(vm.isSourceEnabled("metron")).toBe(true);
    // The enable persists through the draft auto-save.
    expect(store.updateTaggingDefaults).toHaveBeenLastCalledWith(
      expect.objectContaining({
        defaultSources: expect.arrayContaining(["metron"]),
      }),
    );
  });

  test("re-saving credentials respects a deliberately disabled source", async () => {
    const wrapper = mountTab({ configuredSources: ["metron"] });
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.keys.metron = "token";
    await vm.saveCredentials("metron");
    await vm.$nextTick();
    expect(vm.draft.defaultSources).not.toContain("metron");
    expect(vm.isSourceEnabled("metron")).toBe(false);
    // Only the credential save itself hit the server — no defaultSources write.
    expect(store.updateTaggingDefaults).toHaveBeenCalledTimes(1);
  });

  test("a failed credential save does not enable the source", async () => {
    const wrapper = mountTab();
    const vm = wrapper.vm;

    // The server rejected the key; defaults keep no credentials.
    vm.keys.metron = "bad";
    await vm.saveCredentials("metron");
    await vm.$nextTick();
    expect(vm.draft.defaultSources).not.toContain("metron");
    expect(vm.isSourceEnabled("metron")).toBe(false);
  });

  test("only Comic Vine offers a custom URL field", async () => {
    // simyan takes a base_url, so a Comic Vine proxy or mirror works. mokkari
    // hardcodes the metron.cloud endpoint, so Metron has no such field.
    const wrapper = mountTab({
      configuredSources: ["metron", "comicvine"],
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
      configuredSources: ["metron"],
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

  test("each source row carries its own copy, in source order", async () => {
    const wrapper = mountTab({
      configuredSources: ["metron", "comicvine"],
      defaultSources: ["metron", "comicvine"],
    });
    for (const title of wrapper.findAll(".v-expansion-panel-title")) {
      await title.trigger("click");
    }
    await new Promise((resolve) => setTimeout(resolve, 0));

    const ariaLabels = wrapper
      .findAll("[aria-label]")
      .map((el) => el.attributes("aria-label"))
      .filter((label) => /Comic Vine|Metron Cloud/v.test(label));
    expect(ariaLabels).toEqual([
      "Enable Metron Cloud",
      "Reorder Metron Cloud: drag, or press the up and down arrow keys",
      "Enable Comic Vine",
      "Reorder Comic Vine: drag, or press the up and down arrow keys",
    ]);
    const [metronPanel, comicvinePanel] = wrapper.findAll(".sourcePanel");
    expect(metronPanel.find(".adminCardTitle").text()).toBe("Metron Cloud");
    expect(metronPanel.find(".adminHint").text()).toBe(
      "Generate an API key at Metron Cloud API Tokens",
    );
    expect(metronPanel.find(".adminHint a").attributes("href")).toBe(
      "https://metron.cloud/accounts/tokens/",
    );
    expect(comicvinePanel.find(".adminCardTitle").text()).toBe("Comic Vine");
    expect(comicvinePanel.find(".adminHint").text()).toBe(
      "Get an API key from the Comic Vine API",
    );
    expect(comicvinePanel.find(".adminHint a").attributes("href")).toBe(
      "https://comicvine.gamespot.com/api/",
    );
    const [, comicvineClear] = wrapper.findAllComponents(ConfirmDialog);
    expect(comicvineClear.props()).toMatchObject({
      buttonText: "Clear API Key",
      titleText: "Clear Comic Vine API Key",
      text: "Remove the saved Comic Vine API key and custom URL?",
    });
  });

  test("saving sends only the API key, never a username or password", async () => {
    const wrapper = mountTab();
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.keys.metron = "token";
    await vm.saveCredentials("metron");
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      metronKey: "token",
    });
    // The field is cleared so a saved key is never left sitting in the form.
    expect(vm.keys.metron).toBe("");
  });

  test("clearing sends a blank key", async () => {
    const wrapper = mountTab({ configuredSources: ["metron"] });
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.clearCredentials("metron");
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      metronKey: "",
    });
  });

  test("a custom URL saves on its own, without an API key", async () => {
    const wrapper = mountTab();
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.urls.comicvine = "https://cv.example.com/api";
    await vm.saveCredentials("comicvine");
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      comicvineUrl: "https://cv.example.com/api",
    });
    expect(vm.urls.comicvine).toBe("");
    // A url is not a credential, so it must not enable the source.
    expect(vm.draft.defaultSources).not.toContain("comicvine");
  });

  test("clearing the Comic Vine key clears the custom URL too", () => {
    const wrapper = mountTab({ configuredSources: ["comicvine"] });
    const store = useAdminStore();

    wrapper.vm.clearCredentials("comicvine");
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      comicvineKey: "",
      comicvineUrl: "",
    });
  });

  test("testing Comic Vine validates against the typed URL", async () => {
    const wrapper = mountTab({ configuredSources: ["comicvine"] });
    const vm = wrapper.vm;
    const store = useAdminStore();

    vm.urls.comicvine = "https://cv.example.com/api";
    await vm.testCredentials("comicvine");
    expect(store.validateTaggingCredentials).toHaveBeenCalledWith({
      source: "comicvine",
      comicvineUrl: "https://cv.example.com/api",
    });
  });

  test("a stored key can be tested without retyping it", () => {
    const vm = mountTab({ configuredSources: ["metron"] }).vm;
    expect(vm.canTest("metron")).toBe(true);

    const unconfigured = mountTab().vm;
    expect(unconfigured.canTest("metron")).toBe(false);
  });

  test("toggling one source leaves the other untouched", async () => {
    const wrapper = mountTab({
      configuredSources: ["metron", "comicvine"],
      defaultSources: ["comicvine"],
    });
    const vm = wrapper.vm;
    expect(vm.isSourceEnabled("comicvine")).toBe(true);

    vm.setSourceEnabled("metron", true);
    await vm.$nextTick();
    expect(vm.draft.defaultSources).toEqual(
      expect.arrayContaining(["comicvine", "metron"]),
    );
    expect(vm.isSourceEnabled("comicvine")).toBe(true);
  });
});

function mountBoth(defaultSources) {
  return mountTab({
    configuredSources: ["metron", "comicvine"],
    defaultSources,
  });
}

describe("AdminTaggingTab — source priority order", () => {
  test("enabling a source appends it at the end (lowest priority)", async () => {
    const vm = mountBoth(["comicvine"]).vm;
    vm.setSourceEnabled("metron", true);
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
      configuredSources: ["comicvine"],
      defaultSources: ["comicvine"],
    }).vm;
    // Metron isn't in the priority list — it sinks below the enabled rows.
    expect(off.sourceRowStyle("metron")).toEqual({ order: 99 });
  });

  test("a source without credentials sinks below, even if listed", () => {
    // Its key was cleared, but it lingers at the top of defaultSources.
    const vm = mountTab({
      configuredSources: ["comicvine"],
      defaultSources: ["metron", "comicvine"],
    }).vm;
    expect(vm.sourceRowStyle("comicvine")).toEqual({ order: 0 });
    expect(vm.sourceRowStyle("metron")).toEqual({ order: 99 });
  });
});

const ALL_SOURCES = ["metron", "comicvine", "versedb"];

function modeButton(wrapper, label) {
  return wrapper
    .find(".sourcesMode")
    .findAll("button")
    .find((button) => button.text() === label);
}

function rowRank(wrapper, label) {
  const rank = sourceRowFor(wrapper, label).find(".sourceRank");
  return rank.exists() ? rank.text() : "";
}

function rowRole(wrapper, label) {
  const role = sourceRowFor(wrapper, label).find(".sourceRole");
  return role.exists() ? role.text() : "";
}

function sourceRowFor(wrapper, label) {
  return wrapper
    .findAll(".sourceRow")
    .find((row) => row.find(".adminCardTitle").text() === label);
}

describe("AdminTaggingTab — mode switch, ranks and roles", () => {
  test("the switch above the list sets Merge all sources and saves", async () => {
    const wrapper = mountTab({
      configuredSources: ALL_SOURCES,
      defaultSources: ["metron", "comicvine"],
      mergeAllSources: false,
    });
    const store = useAdminStore();

    await modeButton(wrapper, "Merge all sources").trigger("click");
    expect(wrapper.vm.draft.mergeAllSources).toBe(true);
    expect(store.updateTaggingDefaults).toHaveBeenLastCalledWith(
      expect.objectContaining({ mergeAllSources: true }),
    );

    await modeButton(wrapper, "First match").trigger("click");
    expect(wrapper.vm.draft.mergeAllSources).toBe(false);
  });

  test("merging is disabled with one enabled source, and says why", () => {
    const one = mountTab({
      configuredSources: ALL_SOURCES,
      defaultSources: ["metron"],
    });
    expect(modeButton(one, "Merge all sources").element.disabled).toBe(true);
    expect(modeButton(one, "First match").element.disabled).toBe(false);
    expect(one.find(".sourcesModeHint").text()).toBe(
      "Merging needs two or more enabled sources: enable another one below.",
    );

    const two = mountTab({
      configuredSources: ALL_SOURCES,
      defaultSources: ["metron", "comicvine"],
    });
    expect(modeButton(two, "Merge all sources").element.disabled).toBe(false);
    expect(two.find(".sourcesModeHint").text()).toContain(
      "roughly multiplies online API calls",
    );
  });

  test("enabled sources are numbered in priority order", () => {
    const wrapper = mountTab({
      // VerseDB lingers without credentials, so it is not ranked.
      configuredSources: ["metron", "comicvine"],
      defaultSources: ["comicvine", "versedb", "metron"],
    });
    expect(rowRank(wrapper, "Comic Vine")).toBe("1");
    expect(rowRank(wrapper, "Metron Cloud")).toBe("2");
    expect(rowRank(wrapper, "VerseDB")).toBe("");
  });

  test("first match: the top source is tried first, the rest only if no match", () => {
    const wrapper = mountTab({
      configuredSources: ALL_SOURCES,
      defaultSources: ["comicvine", "metron", "versedb"],
      mergeAllSources: false,
    });
    expect(rowRole(wrapper, "Comic Vine")).toBe("Tried first");
    expect(rowRole(wrapper, "Metron Cloud")).toBe("If no match");
    expect(rowRole(wrapper, "VerseDB")).toBe("If no match");
    expect(
      sourceRowFor(wrapper, "Comic Vine").find(".sourceRole").classes(),
    ).toContain("sourceRoleLead");
  });

  test("merging: the top source wins conflicts, the rest fill gaps", async () => {
    const wrapper = mountTab({
      configuredSources: ALL_SOURCES,
      defaultSources: ["comicvine", "metron", "versedb"],
      mergeAllSources: false,
    });
    await modeButton(wrapper, "Merge all sources").trigger("click");
    expect(rowRole(wrapper, "Comic Vine")).toBe("Wins conflicts");
    expect(rowRole(wrapper, "Metron Cloud")).toBe("Fills gaps");
    expect(rowRole(wrapper, "VerseDB")).toBe("Fills gaps");
  });

  test("a lone enabled source is the only source, and others have no role", () => {
    const wrapper = mountTab({
      configuredSources: ["metron", "comicvine"],
      defaultSources: ["metron"],
      mergeAllSources: true,
    });
    expect(rowRole(wrapper, "Metron Cloud")).toBe("Only source");
    expect(rowRole(wrapper, "Comic Vine")).toBe("");
  });
});

function handleFor(wrapper, label) {
  return sourceRowFor(wrapper, label).find(".sourceHandle");
}

function mountThree() {
  const wrapper = mountTab({
    configuredSources: ALL_SOURCES,
    defaultSources: ["metron", "comicvine", "versedb"],
  });
  stubRowBoxes(wrapper);
  return wrapper;
}

/*
 * happy-dom lays nothing out, so give each row a 100px box at the slot its
 * flex ``order`` puts it in, read afresh on every call as a drag moves it.
 */
function stubRowBoxes(wrapper) {
  for (const row of wrapper.findAll(".sourceRow")) {
    row.element.getBoundingClientRect = () => {
      const top = Number(row.element.style.order) * 100;
      return { top, height: 100, bottom: top + 100, left: 0, right: 0 };
    };
  }
}

const PRESS = Object.freeze({ button: 0, pointerId: 1 });

describe("AdminTaggingTab — drag to reorder", () => {
  test("only an enabled source has a drag handle", () => {
    const wrapper = mountTab({
      configuredSources: ALL_SOURCES,
      defaultSources: ["metron"],
    });
    expect(handleFor(wrapper, "Metron Cloud").element.tagName).toBe("BUTTON");
    // The others keep an empty slot so the panels line up.
    expect(handleFor(wrapper, "Comic Vine").element.tagName).toBe("SPAN");
    expect(wrapper.find(".sourceOrderButtons").exists()).toBe(false);
  });

  test("dragging previews the order and saves it once, on release", async () => {
    const wrapper = mountThree();
    const store = useAdminStore();
    const handle = handleFor(wrapper, "Metron Cloud");

    await handle.trigger("pointerdown", { ...PRESS, clientY: 50 });
    expect(sourceRowFor(wrapper, "Metron Cloud").classes()).toContain(
      "sourceRowDragging",
    );
    await handle.trigger("pointermove", { ...PRESS, clientY: 160 });
    expect(rowRank(wrapper, "Comic Vine")).toBe("1");
    expect(rowRank(wrapper, "Metron Cloud")).toBe("2");
    await handle.trigger("pointermove", { ...PRESS, clientY: 260 });
    expect(rowRank(wrapper, "Metron Cloud")).toBe("3");
    expect(store.updateTaggingDefaults).not.toHaveBeenCalled();

    await handle.trigger("pointerup", PRESS);
    expect(wrapper.vm.draft.defaultSources).toEqual([
      "comicvine",
      "versedb",
      "metron",
    ]);
    expect(store.updateTaggingDefaults).toHaveBeenCalledTimes(1);
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith(
      expect.objectContaining({
        defaultSources: ["comicvine", "versedb", "metron"],
      }),
    );
    expect(wrapper.find(".sourceMoveAnnouncement").text()).toBe(
      "Metron Cloud moved to 3 of 3.",
    );
    expect(sourceRowFor(wrapper, "Metron Cloud").classes()).not.toContain(
      "sourceRowDragging",
    );
  });

  test("a cancelled drag puts everything back and saves nothing", async () => {
    const wrapper = mountThree();
    const store = useAdminStore();
    const handle = handleFor(wrapper, "Metron Cloud");

    await handle.trigger("pointerdown", { ...PRESS, clientY: 50 });
    await handle.trigger("pointermove", { ...PRESS, clientY: 260 });
    await handle.trigger("pointercancel", PRESS);
    expect(rowRank(wrapper, "Metron Cloud")).toBe("1");
    expect(wrapper.vm.draft.defaultSources).toEqual([
      "metron",
      "comicvine",
      "versedb",
    ]);
    expect(store.updateTaggingDefaults).not.toHaveBeenCalled();
  });

  test("Escape drops a drag in progress", async () => {
    const wrapper = mountThree();
    const handle = handleFor(wrapper, "Metron Cloud");

    await handle.trigger("pointerdown", { ...PRESS, clientY: 50 });
    await handle.trigger("pointermove", { ...PRESS, clientY: 260 });
    await handle.trigger("keydown", { key: "Escape" });
    await handle.trigger("pointerup", PRESS);
    expect(wrapper.vm.draft.defaultSources).toEqual([
      "metron",
      "comicvine",
      "versedb",
    ]);
  });

  test("only the main button starts a drag", async () => {
    const wrapper = mountThree();
    await handleFor(wrapper, "Metron Cloud").trigger("pointerdown", {
      button: 2,
      pointerId: 1,
      clientY: 50,
    });
    expect(wrapper.vm.dragSource).toBe("");
  });

  test("the arrow keys move a focused handle's source", async () => {
    const wrapper = mountThree();
    const store = useAdminStore();

    await handleFor(wrapper, "VerseDB").trigger("keydown", { key: "ArrowUp" });
    expect(wrapper.vm.draft.defaultSources).toEqual([
      "metron",
      "versedb",
      "comicvine",
    ]);
    expect(store.updateTaggingDefaults).toHaveBeenLastCalledWith(
      expect.objectContaining({
        defaultSources: ["metron", "versedb", "comicvine"],
      }),
    );
    expect(wrapper.find(".sourceMoveAnnouncement").text()).toBe(
      "VerseDB moved to 2 of 3.",
    );

    // Already first: nothing to do.
    await handleFor(wrapper, "Metron Cloud").trigger("keydown", {
      key: "ArrowUp",
    });
    expect(wrapper.vm.draft.defaultSources[0]).toBe("metron");
  });

  test("a move skips a source that lingers without credentials", async () => {
    const wrapper = mountTab({
      configuredSources: ["metron", "comicvine"],
      defaultSources: ["versedb", "metron", "comicvine"],
    });
    await handleFor(wrapper, "Comic Vine").trigger("keydown", {
      key: "ArrowUp",
    });
    expect(wrapper.vm.draft.defaultSources).toEqual([
      "comicvine",
      "metron",
      "versedb",
    ]);
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

  test("offers keep with a hint saying what it rewrites", async () => {
    const wrapper = mountTab({ defaultFormats: ["COMIC_INFO"] });
    const store = useAdminStore();
    expect(formatInput(wrapper, "keep").element.disabled).toBe(false);
    const hint = wrapper
      .findAll(".v-messages__message")
      .map((m) => m.text())
      .find((text) => text.startsWith("Keep other formats"));
    expect(hint).toBeTruthy();
    for (const fact of [
      "comicbox.yaml",
      "never added",
      "PDF",
      "can't be parsed",
      "Tag Write Errors",
    ]) {
      expect(hint).toContain(fact);
    }

    await formatInput(wrapper, "keep").setValue(true);
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith(
      expect.objectContaining({ defaultFormats: ["COMIC_INFO", "keep"] }),
    );
    // Keep is not a format: the one named format still can't be unchecked.
    expect(formatInput(wrapper, "COMIC_INFO").element.disabled).toBe(true);
    expect(wrapper.text()).toContain("At least one format must be written");
  });

  test("keep is disabled while no format is checked", async () => {
    const wrapper = mountTab({ defaultFormats: [] });
    await wrapper.vm.$nextTick();
    expect(formatInput(wrapper, "keep").element.disabled).toBe(true);
    expect(wrapper.text()).toContain("Choose at least one format");
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
