/*
 * Edit Issues on a long list (C7).
 *
 * Each row asked where one step down goes by finding itself in the whole
 * list, so a render of n rows cost n²; the dialog works every row's out
 * in one pass now, the same as before. Hiding an entry replaced the whole
 * list with a fresh fetch; the PATCH answers with the entry, so only its
 * row changes. Building every row's controls at once took seconds on a
 * list of thousands, so the rows render a page at a time.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/api/v4/reading-lists", () => ({
  getEntries: vi.fn(),
  updateEntry: vi.fn(),
  getMappings: vi.fn(() => Promise.resolve({ data: { mappings: [] } })),
}));

import * as API from "@/api/v4/reading-lists";
import ReviewDialog from "@/components/admin/tabs/reading-lists/review-dialog.vue";
import vuetify from "@/plugins/vuetify";

const STUBS = Object.freeze({ VDialog: { template: "<div><slot /></div>" } });

// Hand entries with collections' blocks between them, some back to back.
function longList(length) {
  const live = [null, null, 5, 5, 5, null, 6, 7, 7, null];
  return Array.from({ length }, (_, position) => ({
    pk: 100 + position,
    position,
    seriesName: "Civil War",
    issue: String(position),
    ignored: false,
    liveSource: live[position % live.length],
  }));
}

async function mountReview(entries, { sources = [], ...props } = {}) {
  API.getEntries.mockReset();
  API.getEntries.mockResolvedValue({ data: { entries } });
  const wrapper = mount(ReviewDialog, {
    props: {
      modelValue: true,
      readingList: { pk: 3, name: "CW", sources },
      ...props,
    },
    global: {
      plugins: [createTestingPinia({ createSpy: vi.fn }), vuetify],
      stubs: STUBS,
    },
  });
  await flushPromises();
  return wrapper;
}

// The old rule, row by row: one step down, past a collection's block.
function oldDownTarget(order, entry, isSourced) {
  const next = order[order.indexOf(entry) + 1];
  if (!next) return;
  if (next.liveSource == null) return next.position;
  if (isSourced) return;
  let last = next;
  const after = order.slice(order.indexOf(next) + 1);
  for (const row of after) {
    if (row.liveSource !== next.liveSource) break;
    last = row;
  }
  return last.position;
}

describe("Edit Issues on a long list", () => {
  test.each([
    ["made by hand", []],
    ["with sources", [{ pk: 1 }]],
  ])("each step down is where it was, %s", async (_, sources) => {
    const entries = longList(60);
    const wrapper = await mountReview(entries, { sources });
    const isSourced = sources.length > 0;
    const order = wrapper.vm.ordered;
    for (const entry of order) {
      expect(wrapper.vm.downTargets.get(entry.pk)).toBe(
        oldDownTarget(order, entry, isSourced),
      );
    }
  });

  test("hiding an entry changes its row and fetches nothing", async () => {
    const entries = longList(10);
    const wrapper = await mountReview(entries);
    expect(API.getEntries).toHaveBeenCalledTimes(1);
    API.updateEntry.mockResolvedValue({
      data: { ...entries[0], ignored: true },
    });
    await wrapper.vm.setHidden(wrapper.vm.allEntries[0], true);
    expect(API.updateEntry).toHaveBeenCalledWith(3, 100, { ignored: true });
    expect(API.getEntries).toHaveBeenCalledTimes(1);
    expect(wrapper.vm.allEntries[0].ignored).toBe(true);
    expect(wrapper.vm.allEntries).toHaveLength(entries.length);
    expect(wrapper.emitted("changed")).toHaveLength(1);
  });
});

function entryRows(wrapper) {
  return wrapper.findAll("tbody tr").filter((row) => !row.classes("moreRow"));
}

// Hand entries only: a collection's block shows as one row.
function handList(length) {
  return longList(length).map((entry) => ({ ...entry, liveSource: null }));
}

// Pages of five keep these tests light: the paging is the same at any size.
const PAGE_SIZE = Object.freeze({ pageSize: 5 });

/*
 * happy-dom has no IntersectionObserver. This one records what it watches
 * and reports an intersection when a test says so.
 */
class FakeObserver {
  static instances = [];

  constructor(callback) {
    this.callback = callback;
    this.elements = [];
    FakeObserver.instances.push(this);
  }

  disconnect() {
    this.elements = [];
  }

  observe(element) {
    this.elements.push(element);
  }

  takeRecords() {
    return [];
  }

  unobserve(element) {
    this.elements = this.elements.filter((watched) => watched !== element);
  }
}

// The more row scrolls into view.
function scrollToMore(wrapper) {
  const row = wrapper.find(".moreRow").element;
  for (const observer of watchingMoreRow(wrapper)) {
    observer.callback([{ target: row, isIntersecting: true }]);
  }
}

// The observers watching the more row the page shows now.
function watchingMoreRow(wrapper) {
  const row = wrapper.find(".moreRow").element;
  return FakeObserver.instances.filter((observer) =>
    observer.elements.includes(row),
  );
}

describe("Edit Issues renders a page at a time", () => {
  beforeEach(() => {
    FakeObserver.instances = [];
    vi.stubGlobal("IntersectionObserver", FakeObserver);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("the first page, then more, then back on a new filter", async () => {
    const wrapper = await mountReview(handList(12), PAGE_SIZE);
    expect(entryRows(wrapper)).toHaveLength(5);
    expect(wrapper.find(".moreRow").text()).toContain("5 of 12");
    scrollToMore(wrapper);
    await flushPromises();
    expect(entryRows(wrapper)).toHaveLength(10);
    wrapper.vm.filters = ["hidden"];
    await flushPromises();
    expect(wrapper.vm.shown).toBe(5);
  });

  test("paging goes on after a filter round trip", async () => {
    const wrapper = await mountReview(handList(12), PAGE_SIZE);
    // Nothing is hidden, so the Hidden filter has no more row.
    wrapper.vm.filters = ["hidden"];
    await flushPromises();
    expect(wrapper.find(".moreRow").exists()).toBe(false);
    wrapper.vm.filters = [];
    await flushPromises();

    expect(watchingMoreRow(wrapper)).not.toHaveLength(0);
    scrollToMore(wrapper);
    await flushPromises();
    expect(entryRows(wrapper)).toHaveLength(10);
  });

  test("a row hidden into a filtered page brings its more row", async () => {
    const entries = handList(12).map((entry, index) => ({
      ...entry,
      ignored: index < 5,
    }));
    const wrapper = await mountReview(entries, {
      ...PAGE_SIZE,
      initialFilter: "hidden",
    });
    expect(wrapper.find(".moreRow").exists()).toBe(false);
    API.updateEntry.mockResolvedValue({
      data: { ...entries[5], ignored: true },
    });

    await wrapper.vm.setHidden(wrapper.vm.allEntries[5], true);
    await flushPromises();

    expect(watchingMoreRow(wrapper)).not.toHaveLength(0);
    scrollToMore(wrapper);
    await flushPromises();
    expect(entryRows(wrapper)).toHaveLength(6);
  });

  test("a short list has no more row", async () => {
    const wrapper = await mountReview(handList(4), PAGE_SIZE);
    expect(wrapper.find(".moreRow").exists()).toBe(false);
  });
});
