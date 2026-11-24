/*
 * The admin Reading Lists tab: its store, the table filters, the import
 * payload the Add Lists dialog sends, and the review dialog's reorder.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { setActivePinia } from "pinia";
import { beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/api/v4/reading-lists", () => ({
  getAdminLists: vi.fn(),
  bulkAction: vi.fn(),
  duplicateList: vi.fn(),
  listAction: vi.fn(),
  getMyLists: vi.fn(),
  getSuggestions: vi.fn(),
  getErrors: vi.fn(),
  previewLists: vi.fn(),
  importLists: vi.fn(),
  searchLists: vi.fn(),
  getEntries: vi.fn(),
  reorderEntry: vi.fn(),
  reorderItem: vi.fn(),
  updateEntry: vi.fn(),
  acceptEntries: vi.fn(),
  exportURL: (pk, fmt) => `/export/${pk}/${fmt}`,
  updateItems: vi.fn(),
  getMappings: vi.fn(() => Promise.resolve({ data: { mappings: [] } })),
  deleteMapping: vi.fn(),
  updateAdminList: vi.fn(),
  refreshSource: vi.fn(),
  combineLists: vi.fn(),
  rankSources: vi.fn(),
  removeSource: vi.fn(),
}));

import * as API from "@/api/v4/reading-lists";
import AddListsDialog from "@/components/admin/tabs/reading-lists/add-lists-dialog.vue";
import CombineDialog from "@/components/admin/tabs/reading-lists/combine-dialog.vue";
import ReadingListsTab from "@/components/admin/tabs/reading-lists/reading-lists-tab.vue";
import ReviewDialog from "@/components/admin/tabs/reading-lists/review-dialog.vue";
import SourcesDialog from "@/components/admin/tabs/reading-lists/sources-dialog.vue";
import ReadingListExportMenu from "@/components/reading-list-export-menu.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";
import {
  actionNotice,
  listTypeLabel,
  useReadingListsStore,
} from "@/stores/reading-lists";

const LISTS = Object.freeze([
  {
    pk: 1,
    name: "Civil War",
    listType: "event",
    sources: [{ pk: 10, kind: "tags", attribution: "" }],
    total: 7,
    matched: 7,
    needsReview: 0,
    owner: null,
  },
  {
    pk: 2,
    name: "Civil War (CBRO)",
    listType: "event",
    sources: [{ pk: 11, kind: "catalog", attribution: "cbro" }],
    total: 98,
    matched: 31,
    needsReview: 3,
    owner: null,
  },
]);

// A hand-made list of the admin's with no source, and another user's upload.
const MORE_LISTS = Object.freeze([
  ...LISTS,
  {
    pk: 3,
    name: "Hand Made",
    listType: "",
    sources: [],
    total: 2,
    matched: 2,
    needsReview: 0,
    owner: "admin",
  },
  {
    pk: 4,
    name: "Alice's Upload",
    listType: "",
    sources: [{ pk: 12, kind: "upload", attribution: "" }],
    total: 4,
    matched: 4,
    needsReview: 0,
    owner: "alice",
  },
]);

// An open v-dialog reads visualViewport, which jsdom lacks.
const STUBS = Object.freeze({ VDialog: { template: "<div><slot /></div>" } });

function pinia() {
  return createTestingPinia({ createSpy: vi.fn, stubActions: false });
}

describe("reading lists store", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("loads the table and the error count", async () => {
    API.getAdminLists.mockResolvedValue({
      data: { lists: LISTS, errorCount: 2 },
    });
    const active = pinia();
    const store = useReadingListsStore(active);
    await store.loadLists();
    expect(store.lists).toHaveLength(2);
    expect(store.errorCount).toBe(2);
    expect(store.listsByPk[2].name).toBe("Civil War (CBRO)");
  });
});

describe("reading lists store notices", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("a copy confirms with a notice", async () => {
    API.duplicateList.mockResolvedValue({ data: { pk: 9, name: "CW (copy)" } });
    API.getMyLists.mockResolvedValue({ data: { lists: [] } });
    const active = pinia();
    await useReadingListsStore(active).duplicateList(1);
    expect(useCommonStore(active).notice).toEqual({
      text: 'Copied to your reading lists as "CW (copy)".',
      error: false,
    });
  });

  test("copy to global makes a global copy and says so", async () => {
    API.listAction.mockResolvedValue({ data: { copied: 1 } });
    API.getAdminLists.mockResolvedValue({ data: { lists: LISTS } });
    const active = pinia();
    await useReadingListsStore(active).copyToGlobal(3);
    expect(API.listAction).toHaveBeenCalledWith(3, "copy_global");
    expect(API.getAdminLists).toHaveBeenCalledOnce();
    expect(useCommonStore(active).notice.text).toBe(
      "Copied to a new global reading list.",
    );
  });

  test("an action says what it did, not its id", () => {
    expect(actionNotice("refresh", { queued: 2 })).toBe(
      "Fetching 2 sources again. A list changes if its source did.",
    );
    expect(actionNotice("copy_global", { copied: 1 })).toBe(
      "Copied 1 reading list to global lists.",
    );
    expect(actionNotice("write", { queued: 3, skipped: 1 })).toBe(
      "Writing the story arc into 3 comics. 1 comic in read-only libraries is skipped.",
    );
  });

  test("a bulk Refresh or Complete says why nothing qualified", async () => {
    expect(actionNotice("refresh", { queued: 0 })).toContain(
      "Nothing to fetch again",
    );
    expect(actionNotice("complete", { queued: 0 })).toContain(
      "Metron or Comic Vine arc id",
    );
    API.bulkAction.mockResolvedValue({ data: { queued: 0 } });
    const active = pinia();
    await useReadingListsStore(active).bulk("refresh", [1, 2]);
    expect(useCommonStore(active).notice.text).toContain(
      "Nothing to fetch again",
    );
  });

  test("a failure shows an error notice", async () => {
    API.duplicateList.mockRejectedValue({
      response: { status: 404, data: { detail: "No such reading list." } },
    });
    const active = pinia();
    const copy = await useReadingListsStore(active).duplicateList(1);
    expect(copy).toBeUndefined();
    expect(useCommonStore(active).notice).toEqual({
      text: "No such reading list.",
      error: true,
    });
  });
});

describe("reading lists tab", () => {
  test("filters narrow the table", async () => {
    API.getAdminLists.mockResolvedValue({ data: { lists: LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify] },
    });
    await flushPromises();
    // Nothing ticked is every list, the lists from tags included.
    expect(wrapper.vm.filteredLists.map((list) => list.pk)).toEqual([1, 2]);
    wrapper.vm.reviewOnly = true;
    expect(wrapper.vm.filteredLists.map((list) => list.pk)).toEqual([2]);
    wrapper.vm.reviewOnly = false;
    wrapper.vm.missingOnly = true;
    expect(wrapper.vm.filteredLists.map((list) => list.pk)).toEqual([2]);
    expect(wrapper.vm.sourceLabel(LISTS[1].sources[0])).toBe(
      "DieselTech Catalog · CBRO",
    );
  });

  test("Source is a checklist: a list shows if any source is ticked", async () => {
    API.getAdminLists.mockResolvedValue({ data: { lists: LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify] },
    });
    await flushPromises();
    const shown = () => wrapper.vm.filteredLists.map((list) => list.pk);
    wrapper.vm.kindFilter = ["tags"];
    expect(shown()).toEqual([1]);
    wrapper.vm.kindFilter = ["catalog"];
    expect(shown()).toEqual([2]);
    wrapper.vm.kindFilter = ["tags", "catalog"];
    expect(shown()).toEqual([1, 2]);
    wrapper.vm.kindFilter = [];
    expect(shown()).toEqual([1, 2]);
  });

  test("Source offers the kinds that have lists, with their counts", async () => {
    API.getAdminLists.mockResolvedValue({ data: { lists: LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify] },
    });
    await flushPromises();
    const items = () =>
      wrapper.vm.kindItems.map((item) => [item.value, item.title]);
    expect(items()).toEqual([
      ["tags", "Story Arc Tags (1)"],
      ["catalog", "DieselTech Catalog (1)"],
    ]);
    // A ticked kind stays offered, so it can be unticked.
    wrapper.vm.kindFilter = ["upload"];
    expect(items().map(([value]) => value)).toContain("upload");
  });

  test("Source offers None, for lists with no source", async () => {
    API.getAdminLists.mockResolvedValue({ data: { lists: MORE_LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify] },
    });
    await flushPromises();
    const shown = () => wrapper.vm.filteredLists.map((list) => list.pk);
    expect(wrapper.vm.kindItems[0]).toMatchObject({
      value: "none",
      title: "None (1)",
      name: "None",
    });
    wrapper.vm.kindFilter = ["none"];
    expect(shown()).toEqual([3]);
    wrapper.vm.kindFilter = ["none", "tags"];
    expect(shown()).toEqual([1, 3]);
  });

  test("Visibility is a checklist of Global and each owner", async () => {
    API.getAdminLists.mockResolvedValue({ data: { lists: MORE_LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify] },
    });
    await flushPromises();
    const shown = () => wrapper.vm.filteredLists.map((list) => list.pk);
    expect(
      wrapper.vm.ownerItems.map((item) => [item.value, item.title]),
    ).toEqual([
      [":global", "Global (2)"],
      ["admin", "admin (1)"],
      ["alice", "alice (1)"],
    ]);
    wrapper.vm.ownerFilter = [":global"];
    expect(shown()).toEqual([1, 2]);
    wrapper.vm.ownerFilter = ["admin"];
    expect(shown()).toEqual([3]);
    wrapper.vm.ownerFilter = [":global", "alice"];
    expect(shown()).toEqual([1, 2, 4]);
    // Source and Visibility both apply.
    wrapper.vm.kindFilter = ["upload"];
    wrapper.vm.ownerFilter = [":global"];
    expect(shown()).toEqual([]);
    wrapper.vm.kindFilter = [];
    wrapper.vm.ownerFilter = [];
    expect(shown()).toEqual([1, 2, 3, 4]);
  });

  test("there is no separate Show lists from tags checkbox", async () => {
    API.getAdminLists.mockResolvedValue({ data: { lists: LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify] },
    });
    await flushPromises();
    expect(wrapper.text()).not.toContain("Show lists from tags");
    const source = wrapper.findComponent({ name: "VSelect" });
    expect(source.props("multiple")).toBe(true);
  });

  test("an empty table says why", async () => {
    API.getAdminLists.mockResolvedValue({ data: { lists: [] } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify] },
    });
    await flushPromises();
    expect(wrapper.text()).toContain("No reading lists yet.");
    const store = useReadingListsStore();
    store.lists = [LISTS[0]];
    wrapper.vm.search = "nothing like it";
    await flushPromises();
    expect(wrapper.text()).toContain("No lists match these filters.");
  });

  test("only global lists with comics may be written to files", async () => {
    const personal = { ...LISTS[1], pk: 3, owner: "aj" };
    const empty = { ...LISTS[1], pk: 4, matched: 0 };
    API.getAdminLists.mockResolvedValue({
      data: { lists: [...LISTS, personal, empty] },
    });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    API.bulkAction.mockResolvedValue({ data: { queued: 38 } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    expect(wrapper.vm.writeHint(personal)).toBe(
      "A personal list stays in Codex.",
    );
    expect(wrapper.vm.writeHint(empty)).toBe(
      "None of its issues are in your library.",
    );
    wrapper.vm.selected = [2, 3, 4];
    expect(wrapper.vm.selectedWritable.map((list) => list.pk)).toEqual([2]);
    wrapper.vm.confirmWrite(wrapper.vm.selectedWritable);
    expect(wrapper.vm.writeText).toContain("Civil War (CBRO)");
    await wrapper.vm.bulk("write", [2]);
    expect(API.bulkAction).toHaveBeenCalledWith("write", [2]);
  });
});

describe("reading lists tab — management", () => {
  test("Edit Details saves the name and description", async () => {
    setActivePinia(pinia());
    API.updateAdminList.mockResolvedValue({ data: { pk: 2 } });
    API.getAdminLists.mockResolvedValue({ data: { lists: LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const saved = await useReadingListsStore().updateDetails(2, {
      name: "Civil War",
      description: "Heroes take sides.",
    });
    expect(saved).toBe(true);
    expect(API.updateAdminList).toHaveBeenCalledWith(2, {
      name: "Civil War",
      description: "Heroes take sides.",
    });
    expect(API.getSuggestions).toHaveBeenCalled();
  });

  test("saved series mappings show, and can be forgotten", async () => {
    const mapping = {
      pk: 7,
      seriesKey: "the amazing spider man",
      year: 1963,
      series: { pk: 3, name: "Amazing Spider-Man", startYear: 1963 },
    };
    API.getMappings.mockResolvedValue({ data: { mappings: [mapping] } });
    API.getAdminLists.mockResolvedValue({ data: { lists: LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    expect(wrapper.vm.mappingsLabel).toBe("1 saved series mapping");
    wrapper.vm.showMappings = true;
    await flushPromises();
    expect(wrapper.find(".mappingRow").text()).toContain("Amazing Spider-Man");
    await useReadingListsStore().deleteMapping(7);
    expect(API.deleteMapping).toHaveBeenCalledWith(7);
  });

  test("a reading list job shows its progress on the tab", async () => {
    API.getAdminLists.mockResolvedValue({ data: { lists: LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    useAdminStore().activeLibrarianStatuses = [
      { id: 1, statusType: "RLF", active: true, complete: 2, total: 9 },
      { id: 2, statusType: "IRT", active: true, complete: 0, total: 1 },
    ];
    await flushPromises();
    expect(wrapper.vm.listStatuses.map((status) => status.id)).toEqual([1]);
  });
});

describe("add lists dialog", () => {
  test("a suggested combination is preselected and sent with Import", async () => {
    API.previewLists.mockResolvedValue({
      data: {
        cards: [
          {
            token: "abc",
            kind: "upload",
            ref: "cw.cbl",
            name: "Civil War (CBRO)",
            count: 98,
            matched: 31,
            suggestions: [
              { pk: 1, name: "Civil War", verdict: "subset", combine: true },
            ],
          },
          { kind: "metron_list", ref: "5", name: "Civil War", deferred: true },
        ],
      },
    });
    API.importLists.mockResolvedValue({ data: { queued: 1, fetching: 1 } });
    const wrapper = mount(AddListsDialog, {
      props: { modelValue: true },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    wrapper.vm.urls = "https://example.invalid/cw.cbl";
    await wrapper.vm.preview();
    expect(API.previewLists).toHaveBeenCalledWith(
      [],
      [{ kind: "url", ref: "https://example.invalid/cw.cbl" }],
    );
    wrapper.vm.choices["metron_list:5"].private = true;
    await wrapper.vm.doImport();
    expect(API.importLists).toHaveBeenCalledWith([
      { token: "abc", into: 1, private: false, name: "" },
      { kind: "metron_list", ref: "5", into: null, private: true, name: "" },
    ]);
  });
});

function mountDialog(taggingDefaults) {
  const testingPinia = pinia();
  setActivePinia(testingPinia);
  useAdminStore().taggingDefaults = taggingDefaults;
  useAdminStore().loadTaggingDefaults = vi.fn();
  return mount(AddListsDialog, {
    props: { modelValue: true },
    global: { plugins: [testingPinia, vuetify], stubs: STUBS },
  });
}

describe("add lists dialog — opening", () => {
  test("opens on the catalog, first of the tabs, and lists it", async () => {
    API.searchLists.mockResolvedValue({ data: { results: [] } });
    const wrapper = mountDialog({});
    await flushPromises();
    expect(wrapper.vm.tab).toBe("catalog");
    const tabs = wrapper.findAll(".v-tab").map((tab) => tab.text());
    expect(tabs).toEqual([
      "DieselTech Catalog",
      "Files",
      "URL",
      "Metron",
      "Story Arcs",
    ]);
    expect(API.searchLists).toHaveBeenCalledWith("catalog", "", "");
  });

  test("Metron and Comic Vine say why they are off and where to turn them on", () => {
    const wrapper = mountDialog({
      hasMetronCredentials: false,
      hasComicvineCredentials: true,
    });
    expect(wrapper.vm.hasMetron).toBe(false);
    expect(wrapper.vm.hasComicvine).toBe(true);
    expect(wrapper.vm.KEY_NEEDED.metron).toContain("Admin › Tagging");
  });

  test("a summary counts what is picked on every tab", () => {
    API.searchLists.mockResolvedValue({ data: { results: [] } });
    const wrapper = mountDialog({});
    wrapper.vm.pickedCatalog = ["a", "b"];
    wrapper.vm.urls = "https://example.invalid/x.cbl";
    wrapper.vm.metronArcs = "12";
    expect(wrapper.vm.pickSummary).toBe(
      "Picked: 2 catalog lists, 1 URL, 1 story arc",
    );
  });
});

describe("add lists dialog — private Metron lists", () => {
  test("a list Metron keeps private is sent and previews as private", async () => {
    API.previewLists.mockResolvedValue({
      data: {
        cards: [
          {
            kind: "metron_list",
            ref: "7",
            name: "Mine",
            deferred: true,
            private: true,
          },
        ],
      },
    });
    const wrapper = mount(AddListsDialog, {
      props: { modelValue: true },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    wrapper.vm.metronResults = [
      { ref: "7", name: "Mine", curator: "", listType: "", private: true },
    ];
    wrapper.vm.pickedMetron = ["7"];
    await wrapper.vm.preview();
    expect(API.previewLists).toHaveBeenCalledWith(
      [],
      [
        {
          kind: "metron_list",
          ref: "7",
          name: "Mine",
          curator: "",
          listType: "",
          private: true,
        },
      ],
    );
    expect(wrapper.vm.choices["metron_list:7"].private).toBe(true);
  });
});

describe("removeFromList", () => {
  test("says what it removed and what it hid", async () => {
    setActivePinia(pinia());
    API.updateItems.mockResolvedValue({ data: { removed: 1, hidden: 2 } });
    const changed = await useReadingListsStore().removeFromList(5, [1, 2, 3]);
    expect(changed).toBe(true);
    expect(API.updateItems).toHaveBeenCalledWith(5, {
      remove: { comics: [1, 2, 3] },
    });
    expect(useCommonStore().setNotice).toHaveBeenCalledWith(
      "Removed 1 comic, hid 2 comics its sources hold from the list.",
    );
  });
});

describe("list types", () => {
  test("a list from tags reads as a story arc", () => {
    expect(listTypeLabel("story")).toBe("Story Arc");
    expect(listTypeLabel("event")).toBe("Event");
    expect(listTypeLabel("tie-in-order")).toBe("tie in order");
    expect(listTypeLabel("")).toBe("");
  });
});

describe("add lists dialog — story arcs", () => {
  test("arc ids and Comic Vine addresses become arc sources", () => {
    const wrapper = mount(AddListsDialog, {
      props: { modelValue: true },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    wrapper.vm.metronArcs = "12\nnot an id\n";
    wrapper.vm.comicvineArcs =
      "https://comicvine.gamespot.com/civil-war/4045-55766/\n40";
    expect(wrapper.vm.pickedCount).toBe(3);
    expect(wrapper.vm.sources()).toEqual([
      { kind: "metron_arc", ref: "12", name: "Metron arc 12" },
      { kind: "comicvine_arc", ref: "55766", name: "Comic Vine arc 55766" },
      { kind: "comicvine_arc", ref: "40", name: "Comic Vine arc 40" },
    ]);
  });
});

describe("review dialog — loading", () => {
  const ENTRIES = Object.freeze([
    { pk: 1, needsReview: true, ignored: false, comic: { pk: 9 } },
    { pk: 2, needsReview: false, ignored: false, comic: null },
    { pk: 3, needsReview: false, ignored: true, comic: { pk: 8 } },
  ]);

  test("loads once and narrows in the browser", async () => {
    API.getEntries.mockClear();
    API.getEntries.mockResolvedValue({ data: { entries: ENTRIES } });
    const wrapper = mount(ReviewDialog, {
      props: {
        modelValue: true,
        readingList: { pk: 3, name: "CW" },
        initialFilter: "review",
      },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    expect(API.getEntries).toHaveBeenCalledTimes(1);
    expect(API.getEntries).toHaveBeenCalledWith(3, "all");
    expect(wrapper.vm.entries.map((entry) => entry.pk)).toEqual([1]);
    expect(wrapper.vm.reviewCount).toBe(1);
    wrapper.vm.filters = ["missing"];
    await flushPromises();
    expect(wrapper.vm.entries.map((entry) => entry.pk)).toEqual([2]);
    wrapper.vm.filters = ["hidden"];
    expect(wrapper.vm.entries.map((entry) => entry.pk)).toEqual([3]);
    expect(API.getEntries).toHaveBeenCalledTimes(1);
  });

  test("the filter is a checklist: nothing ticked is every issue", async () => {
    // No toggle with an "All" beside choices it overlaps (AJ's rule).
    API.getEntries.mockResolvedValue({ data: { entries: ENTRIES } });
    const wrapper = mount(ReviewDialog, {
      props: { modelValue: true, readingList: { pk: 3, name: "CW" } },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    const labels = wrapper
      .findAll(".reviewFilter .v-chip")
      .map((chip) => chip.text());
    expect(labels).toEqual(["Needs Review", "Missing", "Hidden"]);
    expect(wrapper.vm.filters).toEqual([]);
    expect(wrapper.vm.entries.map((entry) => entry.pk)).toEqual([1, 2, 3]);
    wrapper.vm.filters = ["missing", "hidden"];
    expect(wrapper.vm.entries.map((entry) => entry.pk)).toEqual([2, 3]);
  });

  test("another list clears the rows before its own arrive", async () => {
    API.getEntries.mockResolvedValue({ data: { entries: ENTRIES } });
    const wrapper = mount(ReviewDialog, {
      props: { modelValue: true, readingList: { pk: 3, name: "CW" } },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    const { promise, resolve } = Promise.withResolvers();
    API.getEntries.mockReturnValue(promise);
    await wrapper.setProps({ readingList: { pk: 4, name: "Other" } });
    expect(wrapper.vm.allEntries).toEqual([]);
    expect(wrapper.vm.loading).toBe(true);
    resolve({ data: { entries: [ENTRIES[1]] } });
    await flushPromises();
    expect(wrapper.vm.allEntries.map((entry) => entry.pk)).toEqual([2]);
  });
});

describe("combine dialog", () => {
  test("says why Combine is off, and previews on every open", async () => {
    const testingPinia = pinia();
    setActivePinia(testingPinia);
    useReadingListsStore().lists = LISTS;
    API.combineLists.mockClear();
    API.combineLists.mockResolvedValue({ data: { total: 9 } });
    const wrapper = mount(CombineDialog, {
      props: { modelValue: false, pks: [1] },
      global: { plugins: [testingPinia, vuetify], stubs: STUBS },
    });
    expect(wrapper.vm.disabledReason).toBe(
      "Choose at least two lists to combine.",
    );
    await wrapper.setProps({ pks: [1, 2], modelValue: true });
    await flushPromises();
    expect(wrapper.vm.disabledReason).toBe("");
    expect(API.combineLists).toHaveBeenCalledWith(1, [2], true);
    await wrapper.setProps({ modelValue: false });
    await wrapper.setProps({ modelValue: true });
    await flushPromises();
    expect(API.combineLists).toHaveBeenCalledTimes(2);
  });
});

describe("sources dialog", () => {
  test("reads the live row, fetches one source, stays open for Add", async () => {
    const testingPinia = pinia();
    setActivePinia(testingPinia);
    const store = useReadingListsStore();
    store.lists = LISTS;
    API.refreshSource.mockResolvedValue({ data: { queued: 1 } });
    const wrapper = mount(SourcesDialog, {
      props: { modelValue: true, readingList: LISTS[1] },
      global: { plugins: [testingPinia, vuetify], stubs: STUBS },
    });
    expect(wrapper.vm.sources.map((source) => source.pk)).toEqual([11]);
    store.lists = [
      LISTS[0],
      { ...LISTS[1], sources: [...LISTS[1].sources, { pk: 12, kind: "url" }] },
    ];
    await flushPromises();
    expect(wrapper.vm.sources.map((source) => source.pk)).toEqual([11, 12]);
    await wrapper.vm.refresh({ pk: 12, kind: "url" });
    expect(API.refreshSource).toHaveBeenCalledWith(2, 12);
    wrapper.vm.addSource();
    expect(wrapper.emitted("add-source")).toHaveLength(1);
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });
});

describe("review dialog", () => {
  test("a typed position moves the entry, 0-based", async () => {
    API.getEntries.mockResolvedValue({
      data: {
        entries: [
          { pk: 7, position: 0, seriesName: "Civil War", issue: "1" },
          { pk: 8, position: 1, seriesName: "Civil War", issue: "2" },
        ],
      },
    });
    API.reorderEntry.mockResolvedValue({ data: { position: 0 } });
    const wrapper = mount(ReviewDialog, {
      props: { modelValue: true, readingList: { pk: 3, name: "CW" } },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    await wrapper.vm.move(wrapper.vm.entries[1], 0);
    expect(API.reorderEntry).toHaveBeenCalledWith(3, 8, 0);
  });
});

describe("review dialog — moving an entry", () => {
  const ENTRIES = Object.freeze([
    { pk: 7, position: 0, seriesName: "Civil War", issue: "1" },
    { pk: 8, position: 1, seriesName: "Civil War", issue: "2" },
    { pk: 9, position: 2, seriesName: "Civil War", issue: "3" },
  ]);

  async function mountReview(entries = ENTRIES, sources = []) {
    API.getEntries.mockResolvedValue({ data: { entries } });
    API.reorderEntry.mockResolvedValue({ data: { position: 0 } });
    API.reorderEntry.mockClear();
    const wrapper = mount(ReviewDialog, {
      props: { modelValue: true, readingList: { pk: 3, name: "CW", sources } },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    // The rows are in list order, pk 7 first.
    const row = (pk) => wrapper.findAll("tbody tr")[pk - 7];
    return { wrapper, row };
  }

  // A hand entry, a collection's block of two, another hand entry.
  const WITH_BLOCK = Object.freeze([
    { pk: 7, position: 0, seriesName: "Civil War", issue: "1" },
    { pk: 8, position: 1, seriesName: "X-Men", issue: "1", liveSource: 5 },
    { pk: 9, position: 2, seriesName: "X-Men", issue: "2", liveSource: 5 },
    { pk: 10, position: 3, seriesName: "Civil War", issue: "2" },
  ]);

  test("a held collection is one row, whose Remove removes it", async () => {
    // Its issues used to be a row each, and every control on them was
    // refused: an issue a collection brings is the collection's.
    const items = [
      {
        pk: 5,
        collection: "series",
        targetId: 42,
        label: "X-Men",
        dangling: false,
        count: 2,
        position: 1,
      },
    ];
    API.getEntries.mockResolvedValue({ data: { entries: WITH_BLOCK, items } });
    API.updateItems.mockClear();
    API.updateItems.mockResolvedValue({ data: {} });
    const wrapper = mount(ReviewDialog, {
      props: { modelValue: true, readingList: { pk: 3, name: "CW", sources: [] } },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    const rows = wrapper.findAll("tbody tr");
    expect(rows).toHaveLength(3);
    const held = rows[1];
    expect(held.text()).toContain("X-Men");
    expect(held.text()).toContain("2 issues");
    expect(held.find(".moveUp").exists()).toBe(false);
    expect(held.findAll(".entryActions button")).toHaveLength(1);
    await held.find(".removeItem").trigger("click");
    await flushPromises();
    expect(API.updateItems).toHaveBeenCalledWith(3, {
      remove: { series: [42] },
    });
  });

  test("one step down past a collection's block clears the whole block", async () => {
    const { row } = await mountReview(WITH_BLOCK);
    await row(7).find(".moveDown").trigger("click");
    await flushPromises();
    expect(API.reorderEntry).toHaveBeenLastCalledWith(3, 7, 2);
  });

  test("on a list with sources, issues stay before its collections", async () => {
    const entries = [
      { pk: 7, position: 0, seriesName: "Civil War", issue: "1" },
      { pk: 8, position: 1, seriesName: "Civil War", issue: "2" },
      { pk: 9, position: 2, seriesName: "X-Men", issue: "1", liveSource: 5 },
    ];
    const { row } = await mountReview(entries, [{ pk: 1, kind: "upload" }]);
    expect(row(8).find(".moveDown").attributes("disabled")).toBeDefined();
    expect(row(7).find(".moveDown").attributes("disabled")).toBeUndefined();
  });

  test("the up arrow moves an entry up the list, the down arrow down", async () => {
    const { row } = await mountReview();
    await row(8).find(".moveUp").trigger("click");
    await flushPromises();
    expect(API.reorderEntry).toHaveBeenLastCalledWith(3, 8, 0);
    await row(8).find(".moveDown").trigger("click");
    await flushPromises();
    expect(API.reorderEntry).toHaveBeenLastCalledWith(3, 8, 2);
  });

  test("there is no up from the top, no down from the bottom", async () => {
    const { row } = await mountReview();
    expect(row(7).find(".moveUp").attributes("disabled")).toBeDefined();
    expect(row(7).find(".moveDown").attributes("disabled")).toBeUndefined();
    expect(row(9).find(".moveDown").attributes("disabled")).toBeDefined();
    expect(row(9).find(".moveUp").attributes("disabled")).toBeUndefined();
  });

  test("the position field has no number spinner, whose up counts down the list", async () => {
    const { row } = await mountReview();
    const input = row(8).find(".positionInput input");
    expect(input.attributes("type")).not.toBe("number");
    expect(input.attributes("inputmode")).toBe("numeric");
  });
});

describe("export menu", () => {
  test("offers json-cbl first, then ComicRack CBL", async () => {
    globalThis.visualViewport ??= {
      width: 1024,
      height: 768,
      offsetLeft: 0,
      offsetTop: 0,
      scale: 1,
      addEventListener() {},
      removeEventListener() {},
    };
    const wrapper = mount(ReadingListExportMenu, {
      attachTo: document.body,
      props: { pk: 4 },
      global: { plugins: [pinia(), vuetify] },
    });
    expect(wrapper.find(".exportListItem").text()).toContain("Export");
    await wrapper.find(".exportListItem").trigger("click");
    await flushPromises();
    const links = [...document.querySelectorAll(".v-overlay--active a")].map(
      (a) => [a.textContent.trim(), a.getAttribute("href")],
    );
    expect(links).toEqual([
      ["json-cbl", "/export/4/json-cbl"],
      ["ComicRack CBL", "/export/4/cbl"],
    ]);
    wrapper.unmount();
  });
});

describe("disabled controls say why, in words on the page", () => {
  /*
   * A title never shows on a disabled button, so each reason is text
   * beside the control while it is off (AJ's rule for disabled controls).
   */
  test("the bulk bar's Combine and Write to Files", async () => {
    API.getAdminLists.mockResolvedValue({ data: { lists: MORE_LISTS } });
    API.getSuggestions.mockResolvedValue({ data: { suggestions: [] } });
    const wrapper = mount(ReadingListsTab, {
      global: { plugins: [pinia(), vuetify] },
    });
    await flushPromises();
    // One personal list: too few to combine, and never written to files.
    wrapper.vm.selected = [3];
    await flushPromises();
    const bar = wrapper.find(".bulkBar").text();
    expect(bar).toContain("Select at least two lists to combine them.");
    expect(bar).toContain("Only global lists with issues in your library");
  });

  test("Accept All Best Guesses in Edit Issues", async () => {
    API.getEntries.mockResolvedValue({ data: { entries: [] } });
    const wrapper = mount(ReviewDialog, {
      props: { modelValue: true, readingList: { pk: 3, name: "CW" } },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    expect(wrapper.find(".reviewBar").text()).toContain("No issue needs review.");
  });

  test("Preview and Import in Add Lists", async () => {
    const wrapper = mount(AddListsDialog, {
      props: { modelValue: true },
      global: { plugins: [pinia(), vuetify], stubs: STUBS },
    });
    await flushPromises();
    expect(wrapper.text()).toContain("Pick at least one list on any tab.");
    wrapper.vm.cards = [{ kind: "url", ref: "x", name: "x", error: "Gone." }];
    await flushPromises();
    expect(wrapper.text()).toContain("Every list here failed to load.");
  });

  test("Combine in the combine dialog", async () => {
    const testingPinia = pinia();
    setActivePinia(testingPinia);
    useReadingListsStore().lists = LISTS;
    const wrapper = mount(CombineDialog, {
      props: { modelValue: true, pks: [1] },
      global: { plugins: [testingPinia, vuetify], stubs: STUBS },
    });
    await flushPromises();
    expect(wrapper.text()).toContain("Choose at least two lists to combine.");
  });

  test("a source with nothing to fetch has no Refresh", () => {
    const testingPinia = pinia();
    setActivePinia(testingPinia);
    useReadingListsStore().lists = LISTS;
    const wrapper = mount(SourcesDialog, {
      props: { modelValue: true, readingList: LISTS[0] },
      global: { plugins: [testingPinia, vuetify], stubs: STUBS },
    });
    const titles = wrapper.findAll("button").map((b) => b.attributes("title"));
    expect(titles).not.toContain("Uploads and tags have nothing to fetch.");
    expect(titles).not.toContain("Fetch again");
  });
});
