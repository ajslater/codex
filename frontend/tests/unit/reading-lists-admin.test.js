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
  updateEntry: vi.fn(),
  acceptEntries: vi.fn(),
  exportURL: (pk, fmt) => `/export/${pk}/${fmt}`,
  removeComics: vi.fn(),
  getMappings: vi.fn(() => Promise.resolve({ data: { mappings: [] } })),
  deleteMapping: vi.fn(),
  updateAdminList: vi.fn(),
}));

import * as API from "@/api/v4/reading-lists";
import AddListsDialog from "@/components/admin/tabs/reading-lists/add-lists-dialog.vue";
import ReadingListsTab from "@/components/admin/tabs/reading-lists/reading-lists-tab.vue";
import ReviewDialog from "@/components/admin/tabs/reading-lists/review-dialog.vue";
import ReadingListExportMenu from "@/components/reading-list-export-menu.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";
import { listTypeLabel, useReadingListsStore } from "@/stores/reading-lists";

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
    // The list from tags alone is hidden unless asked for.
    expect(wrapper.vm.filteredLists.map((list) => list.pk)).toEqual([2]);
    expect(wrapper.vm.tagsOnlyCount).toBe(1);
    wrapper.vm.showTagsOnly = true;
    expect(wrapper.vm.filteredLists.map((list) => list.pk)).toEqual([1, 2]);
    wrapper.vm.kindFilter = "catalog";
    expect(wrapper.vm.filteredLists.map((list) => list.pk)).toEqual([2]);
    wrapper.vm.kindFilter = null;
    wrapper.vm.reviewOnly = true;
    expect(wrapper.vm.filteredLists.map((list) => list.pk)).toEqual([2]);
    wrapper.vm.reviewOnly = false;
    wrapper.vm.missingOnly = true;
    expect(wrapper.vm.filteredLists.map((list) => list.pk)).toEqual([2]);
    expect(wrapper.vm.sourceLabel(LISTS[1].sources[0])).toBe(
      "DieselTech Catalog · CBRO",
    );
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
    API.removeComics.mockResolvedValue({ data: { removed: 1, hidden: 2 } });
    const changed = await useReadingListsStore().removeFromList(5, [1, 2, 3]);
    expect(changed).toBe(true);
    expect(API.removeComics).toHaveBeenCalledWith(5, [1, 2, 3]);
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
