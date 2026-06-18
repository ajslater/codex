/*
 * Tests for ``stores/browser-select-many.js`` — shift-click range
 * selection dispatching. Plain ``toggleItem`` semantics are pinned
 * indirectly via the ``selectItemAt`` fall-through cases (no shift,
 * no anchor, anchor off-page). The store reads the current page's
 * item list from ``useBrowserStore``, so each test seeds that
 * store with a minimal ``page`` payload.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useBrowserStore } from "@/stores/browser";
import { useBrowserSelectManyStore } from "@/stores/browser-select-many";

const _row = (group, pk, name = `${group}-${pk}`) => ({
  collection: group,
  ids: [pk],
  pk,
  name,
});

function seedPage({ rows, collections, books }) {
  const browserStore = useBrowserStore();
  browserStore.page = {
    rows: rows ?? null,
    collections: collections ?? [],
    books: books ?? [],
  };
}

function selectedNames(store) {
  return [...store.selectedItems.values()].map((i) => i.name);
}

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("useBrowserSelectManyStore — initial state", () => {
  it("starts inactive with an empty selection and no anchor", () => {
    const store = useBrowserSelectManyStore();
    expect(store.active).toBe(false);
    expect(store.selectedItems.size).toBe(0);
    expect(store.lastAnchorKey).toBeNull();
  });
});

describe("useBrowserSelectManyStore — toggleItem anchor tracking", () => {
  it("sets lastAnchorKey to the toggled item", () => {
    seedPage({ collections: [_row("s", 1), _row("s", 2)] });
    const store = useBrowserSelectManyStore();
    store.toggleItem(_row("s", 1));
    expect(store.lastAnchorKey).toBe("s:1");
    expect(store.active).toBe(true);
  });

  it("clears the anchor when the last item is untoggled", () => {
    seedPage({ collections: [_row("s", 1)] });
    const store = useBrowserSelectManyStore();
    store.toggleItem(_row("s", 1));
    store.toggleItem(_row("s", 1));
    expect(store.lastAnchorKey).toBeNull();
    expect(store.active).toBe(false);
  });
});

describe("useBrowserSelectManyStore — selectItemAt no-shift fallback", () => {
  it("plain click delegates to toggleItem", () => {
    seedPage({ collections: [_row("s", 1), _row("s", 2)] });
    const store = useBrowserSelectManyStore();
    store.selectItemAt(_row("s", 1), { shift: false });
    expect(store.selectedItems.size).toBe(1);
    expect(store.lastAnchorKey).toBe("s:1");
  });

  it("plain click on an already-selected item deselects it", () => {
    seedPage({ collections: [_row("s", 1)] });
    const store = useBrowserSelectManyStore();
    store.selectItemAt(_row("s", 1));
    store.selectItemAt(_row("s", 1));
    expect(store.selectedItems.size).toBe(0);
  });

  it("shift-click without an anchor falls back to toggle", () => {
    seedPage({ collections: [_row("s", 1), _row("s", 2)] });
    const store = useBrowserSelectManyStore();
    // No prior interaction → no anchor → must act like a plain click.
    store.selectItemAt(_row("s", 1), { shift: true });
    expect(store.selectedItems.size).toBe(1);
    expect(selectedNames(store)).toEqual(["s-1"]);
  });
});

describe("useBrowserSelectManyStore — selectItemAt range fill", () => {
  it("fills the range forward (anchor before target)", () => {
    const collections = [1, 2, 3, 4, 5].map((pk) => _row("s", pk));
    seedPage({ collections });
    const store = useBrowserSelectManyStore();
    store.selectItemAt(collections[0]);
    store.selectItemAt(collections[3], { shift: true });
    expect(selectedNames(store).sort()).toEqual(["s-1", "s-2", "s-3", "s-4"]);
    // Target becomes the new anchor for further extensions.
    expect(store.lastAnchorKey).toBe("s:4");
  });

  it("fills the range backward (anchor after target)", () => {
    const collections = [1, 2, 3, 4, 5].map((pk) => _row("s", pk));
    seedPage({ collections });
    const store = useBrowserSelectManyStore();
    store.selectItemAt(collections[3]);
    store.selectItemAt(collections[1], { shift: true });
    expect(selectedNames(store).sort()).toEqual(["s-2", "s-3", "s-4"]);
    expect(store.lastAnchorKey).toBe("s:2");
  });

  it("range fill sets — never unsets — previously-selected items", () => {
    const collections = [1, 2, 3, 4].map((pk) => _row("s", pk));
    seedPage({ collections });
    const store = useBrowserSelectManyStore();
    // Two plain clicks → s:1 and s:3 selected; anchor follows to s:3.
    store.selectItemAt(collections[0]);
    store.selectItemAt(collections[2]);
    expect(selectedNames(store).sort()).toEqual(["s-1", "s-3"]);
    // Shift-click from anchor s:3 back to s:1 — fills [s:1, s:2, s:3]
    // by SET, not toggle. s:1 and s:3 (already selected) stay
    // selected; s:2 is newly added.
    store.selectItemAt(collections[0], { shift: true });
    expect(selectedNames(store).sort()).toEqual(["s-1", "s-2", "s-3"]);
  });
});

describe("useBrowserSelectManyStore — selectItemAt with off-page anchor", () => {
  it("falls back to toggle when the anchor is not on the current page", () => {
    seedPage({ collections: [_row("s", 1), _row("s", 2)] });
    const store = useBrowserSelectManyStore();
    store.selectItemAt(_row("s", 1));
    // Page changes — anchor's pk is no longer in the visible list.
    seedPage({ collections: [_row("s", 10), _row("s", 11), _row("s", 12)] });
    store.selectItemAt(_row("s", 12), { shift: true });
    // Anchor was stale; treated as plain click on s:12 only.
    expect(selectedNames(store).sort()).toEqual(["s-1", "s-12"]);
    expect(store.lastAnchorKey).toBe("s:12");
  });
});

describe("useBrowserSelectManyStore — mixed visible lists", () => {
  it("spans collections + books in cover mode", () => {
    seedPage({
      collections: [_row("s", 1), _row("s", 2)],
      books: [_row("c", 100), _row("c", 101)],
    });
    const store = useBrowserSelectManyStore();
    store.selectItemAt(_row("s", 2));
    store.selectItemAt(_row("c", 100), { shift: true });
    expect(selectedNames(store).sort()).toEqual(["c-100", "s-2"]);
  });

  it("prefers rows over collections+books when both are populated", () => {
    seedPage({
      rows: [_row("c", 1), _row("c", 2), _row("c", 3)],
      // Stale cover-mode lists left on the page should be ignored.
      collections: [_row("s", 99)],
      books: [_row("c", 99)],
    });
    const store = useBrowserSelectManyStore();
    store.selectItemAt(_row("c", 1));
    store.selectItemAt(_row("c", 3), { shift: true });
    expect(selectedNames(store).sort()).toEqual(["c-1", "c-2", "c-3"]);
  });
});

describe("useBrowserSelectManyStore — anchor reset on selection clear", () => {
  it("clearSelection drops the anchor", () => {
    seedPage({ collections: [_row("s", 1), _row("s", 2)] });
    const store = useBrowserSelectManyStore();
    store.selectItemAt(_row("s", 1));
    store.clearSelection();
    expect(store.lastAnchorKey).toBeNull();
    // Subsequent shift-click without a new anchor falls back to toggle.
    store.selectItemAt(_row("s", 2), { shift: true });
    expect(selectedNames(store)).toEqual(["s-2"]);
  });

  it("deactivate drops the anchor", () => {
    seedPage({ collections: [_row("s", 1)] });
    const store = useBrowserSelectManyStore();
    store.selectItemAt(_row("s", 1));
    store.deactivate();
    expect(store.lastAnchorKey).toBeNull();
    expect(store.active).toBe(false);
  });
});
