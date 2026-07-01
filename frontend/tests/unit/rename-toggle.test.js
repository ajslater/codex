/*
 * Tests for the comicbox "rename files" toggle across the UI.
 *
 * Behavior locked in here:
 *   - The online-tag store forwards `rename` to the start and by-id endpoints.
 *   - The edit panel seeds its rename toggle from the admin default and lets
 *     the toggle alone enable Save (rename-only, no tag edits).
 *   - The admin Tagging tab renders a "Rename files" default and binds it.
 */
import { createTestingPinia } from "@pinia/testing";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, test, vi } from "vitest";

vi.mock("@/api/v4/base", () => ({
  HTTP: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

import { HTTP } from "@/api/v4/base";
import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import TaggingTab from "@/components/admin/tabs/tagging-tab.vue";
import vuetify from "@/plugins/vuetify";
import { useOnlineTagStore } from "@/stores/online-tag";

describe("useOnlineTagStore — rename forwarding", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("forwards rename to the start endpoint", async () => {
    const store = useOnlineTagStore();
    HTTP.post.mockResolvedValue({ data: { sessionId: "s1" } });
    await store.startSession({
      collection: "comics",
      pks: [1],
      sources: ["metron"],
      mode: "auto",
      promptsMode: "ask",
      deleteOriginal: false,
      mergeAllSources: false,
      rename: true,
    });
    expect(HTTP.post).toHaveBeenCalledWith(
      "/admin/tag-sessions/start",
      expect.objectContaining({ rename: true }),
    );
  });

  it("forwards rename to the by-id endpoint", async () => {
    const store = useOnlineTagStore();
    HTTP.post.mockResolvedValue({ data: { source: "metron", id: 1 } });
    await store.tagById({
      collection: "comics",
      pk: 1,
      identifier: "metron:1",
      rename: true,
    });
    expect(HTTP.post).toHaveBeenCalledWith(
      "/admin/tag-by-id",
      expect.objectContaining({ rename: true }),
    );
  });
});

let mountedWrappers = [];

async function mountEditPanel(renameFiles, md = {}, ids = [1], childCount = 0) {
  const pinia = createTestingPinia({
    initialState: {
      metadata: { md },
      admin: {
        taggingDefaults: { defaultFormats: ["COMIC_INFO"], renameFiles },
      },
      browser: { settings: { twentyFourHourTime: false } },
    },
  });
  const wrapper = mount(EditPanel, {
    props: { book: { pk: ids[0], collection: "comics", ids, childCount } },
    // Stub VDialog: its Vuetify overlay reads visualViewport, which the test
    // DOM lacks; these tests assert confirmDialog state, not the overlay.
    global: { plugins: [pinia, vuetify], stubs: { VDialog: true } },
  });
  mountedWrappers.push(wrapper);
  await flushPromises();
  return wrapper;
}

describe("EditPanel — rename toggle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // The rename preview debounce hits the preflight endpoint; give it a
    // benign default so a fired timer never rejects.
    HTTP.post.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    // Unmount so beforeUnmount clears the debounce timer; otherwise a pending
    // single-comic preview fetch can fire during a later test.
    mountedWrappers.forEach((wrapper) => wrapper.unmount());
    mountedWrappers = [];
  });

  test("seeds the toggle from the admin default", async () => {
    const wrapper = await mountEditPanel(true);
    expect(wrapper.vm.renameFile).toBe(true);
  });

  test("fetches the comicbox filename preview when rename is on", async () => {
    HTTP.post.mockResolvedValue({
      data: { filenamePreviews: [{ old: "c.cbz", new: "Series #001.cbz" }] },
    });
    const wrapper = await mountEditPanel(true);
    await wrapper.vm.fetchRenamePreview();
    expect(HTTP.post).toHaveBeenCalledWith(
      "/admin/tag-write/preflight",
      expect.objectContaining({ patch: expect.any(String) }),
    );
    expect(wrapper.vm.renamePreviews).toEqual([
      { old: "c.cbz", new: "Series #001.cbz" },
    ]);
    expect(wrapper.vm.previewLabel).toBe("Series #001.cbz");
  });

  test("rename alone enables Save with no tag edits", async () => {
    const wrapper = await mountEditPanel(true);
    expect(wrapper.vm.hasChanges).toBe(false);
    expect(wrapper.vm.canSave).toBe(true);
  });

  test("the button reads 'Rename File' for a rename-only edit", async () => {
    const wrapper = await mountEditPanel(true);
    expect(wrapper.vm.saveButtonLabel).toBe("Rename File");
    // Altering a tag switches it back to Save Tags.
    wrapper.vm.patch.summary = "edited";
    await flushPromises();
    expect(wrapper.vm.hasChanges).toBe(true);
    expect(wrapper.vm.saveButtonLabel).toBe("Save Tags");
  });

  test("Save stays disabled with no edits and rename off", async () => {
    const wrapper = await mountEditPanel(false);
    expect(wrapper.vm.renameFile).toBe(false);
    expect(wrapper.vm.canSave).toBe(false);
  });

  test("always confirms when rename is on, even for one small edit", async () => {
    HTTP.post.mockResolvedValue({
      data: {
        total: 1,
        needConversion: 0,
        filenamePreviews: [{ old: "c.cbz", new: "New.cbz" }],
      },
    });
    const wrapper = await mountEditPanel(true);
    await wrapper.vm.preSave();
    expect(wrapper.vm.confirmDialog).toBe(true);
    // The write endpoint must not be hit until the user confirms.
    expect(HTTP.post).not.toHaveBeenCalledWith(
      "/admin/tag-write",
      expect.anything(),
    );
  });

  test("a small tag-only edit saves without a dialog", async () => {
    HTTP.post.mockResolvedValue({
      data: { total: 1, needConversion: 0, filenamePreviews: [] },
    });
    const wrapper = await mountEditPanel(false);
    wrapper.vm.patch.summary = "edited";
    await flushPromises();
    await wrapper.vm.preSave();
    expect(wrapper.vm.confirmDialog).toBe(false);
    expect(HTTP.post).toHaveBeenCalledWith(
      "/admin/tag-write",
      expect.anything(),
    );
  });

  test("shows the current filename when rename is off", async () => {
    const wrapper = await mountEditPanel(false, {
      path: "/comics/Old Name.cbz",
    });
    expect(wrapper.vm.renameFile).toBe(false);
    expect(wrapper.vm.currentFileName).toBe("Old Name.cbz");
    expect(wrapper.vm.previewLabel).toBe("Old Name.cbz");
  });

  test("switches to the new-name preview when rename is on", async () => {
    HTTP.post.mockResolvedValue({
      data: {
        filenamePreviews: [{ old: "Old Name.cbz", new: "New Name #001.cbz" }],
      },
    });
    const wrapper = await mountEditPanel(true, {
      path: "/comics/Old Name.cbz",
    });
    await wrapper.vm.fetchRenamePreview();
    expect(wrapper.vm.previewLabel).toBe("New Name #001.cbz");
  });

  test("pluralizes checkbox and button and skips the inline pill for many", async () => {
    const wrapper = await mountEditPanel(true, {}, [1, 2, 3]);
    expect(wrapper.vm.isMultipleComics).toBe(true);
    expect(wrapper.vm.renameCheckboxLabel).toBe("Rename files");
    // Rename-only across multiple comics.
    expect(wrapper.vm.saveButtonLabel).toBe("Rename Files");
    // No live per-file fetch for multi-comic, and no misleading first-file pill.
    expect(HTTP.post).not.toHaveBeenCalled();
    expect(wrapper.find(".renamePreviewInline").exists()).toBe(false);
  });

  test("singular labels for a single comic", async () => {
    const wrapper = await mountEditPanel(true, {}, [1]);
    expect(wrapper.vm.isMultipleComics).toBe(false);
    expect(wrapper.vm.renameCheckboxLabel).toBe("Rename file");
    expect(wrapper.vm.saveButtonLabel).toBe("Rename File");
  });

  test("pluralizes for a container edit (childCount, single id)", async () => {
    // Editing a whole series: one container id but many child comics.
    const wrapper = await mountEditPanel(true, {}, [5], 20);
    expect(wrapper.vm.isMultipleComics).toBe(true);
    expect(wrapper.vm.renameCheckboxLabel).toBe("Rename files");
    expect(wrapper.vm.saveButtonLabel).toBe("Rename Files");
  });

  test("reports a no-op when the name already matches the scheme", async () => {
    const wrapper = await mountEditPanel(true, { path: "/comics/Match.cbz" });
    wrapper.vm.renamePreviews = [{ old: "Match.cbz", new: "Match.cbz" }];
    await flushPromises();
    expect(wrapper.vm.renameWillChange).toBe(false);
    expect(wrapper.vm.renameChanges).toEqual([]);
    expect(wrapper.vm.renameNoop).toBe(true);
    expect(wrapper.vm.renamePreviewTitle).toBe(
      "Already matches the comicbox scheme",
    );
    // The inline pill isn't styled as a pending change.
    const pill = wrapper.find(".renamePreviewInline");
    expect(pill.exists()).toBe(true);
    expect(pill.classes()).not.toContain("renamePreviewActive");
  });

  test("counts only real renames and reports the unchanged", async () => {
    const wrapper = await mountEditPanel(true, {}, [1, 2, 3]);
    wrapper.vm.confirmInfo = { total: 3, needConversion: 0, skipped: 0 };
    wrapper.vm.renamePreviews = [
      { old: "a.cbz", new: "A #001.cbz" },
      { old: "b.cbz", new: "b.cbz" },
      { old: "c.cbz", new: "" },
    ];
    await flushPromises();
    expect(wrapper.vm.renameChanges).toEqual([
      { old: "a.cbz", new: "A #001.cbz" },
    ]);
    expect(wrapper.vm.renameUnchangedCount).toBe(1);
    // One file changes, so it's not a pure no-op.
    expect(wrapper.vm.renameNoop).toBe(false);
  });

  test("inline preview is styled active for a real rename", async () => {
    const wrapper = await mountEditPanel(true, { path: "/comics/old.cbz" });
    wrapper.vm.renamePreviews = [{ old: "old.cbz", new: "New #001.cbz" }];
    await flushPromises();
    const pill = wrapper.find(".renamePreviewInline");
    expect(pill.text()).toContain("New #001.cbz");
    expect(pill.classes()).toContain("renamePreviewActive");
  });
});

const BASE_DEFAULTS = {
  defaultFormats: ["COMIC_INFO"],
  deleteOriginal: false,
  renameFiles: true,
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

describe("AdminTaggingTab — rename default", () => {
  test("renders the rename default bound to the draft", () => {
    const pinia = createTestingPinia({
      initialState: { admin: { taggingDefaults: BASE_DEFAULTS } },
    });
    const wrapper = mount(TaggingTab, {
      global: {
        plugins: [pinia, vuetify],
        stubs: {
          TagWriteErrorsPanel: true,
          ValidationChip: true,
          ConfirmDialog: true,
        },
      },
    });
    expect(wrapper.text()).toContain("Rename files to the comicbox scheme");
    expect(wrapper.vm.draft.renameFiles).toBe(true);
  });
});

export default {};
