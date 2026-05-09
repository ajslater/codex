/*
 * Pure-function tests for ``smartInsertIndex`` exported from the
 * browser table column picker. The helper consumes an ordered draft
 * of column keys and a key to insert, returning the splice index.
 *
 * Algorithm under test: if the draft's canonical ranks (defined by
 * ``_CATEGORIES`` flattened) are strictly increasing, splice the
 * new key into the unique slot that keeps the sequence sorted;
 * otherwise append. Orphans (keys not in any category) rank at
 * ``+Infinity`` and always sort to the tail.
 */
import { describe, expect, it } from "vitest";

import { smartInsertIndex } from "@/components/browser/table/browser-table-column-picker.vue";

/*
 * Canonical-rank reference for the cases below — kept here so the
 * test reads as a story rather than an opaque number puzzle:
 *   cover=0, favorite=1, publisher_name=2, imprint_name=3,
 *   series_name=4, volume_name=5, issue=6, name=7, child_count=8,
 *   file_name=9, size=10, page_count=11, file_type=12,
 *   year=13, …
 */

describe("smartInsertIndex — canonical-order drafts", () => {
  it("inserts favorite right after cover", () => {
    const draft = ["cover", "name", "child_count"];
    expect(smartInsertIndex(draft, "favorite")).toBe(1);
  });

  it("inserts favorite first when cover is absent", () => {
    const draft = ["name", "child_count"];
    expect(smartInsertIndex(draft, "favorite")).toBe(0);
  });

  it("inserts imprint_name after publisher_name when both are present", () => {
    const draft = ["cover", "publisher_name", "name", "child_count"];
    expect(smartInsertIndex(draft, "imprint_name")).toBe(2);
  });

  it("inserts imprint_name after favorite when publisher is absent", () => {
    const draft = ["cover", "favorite", "name"];
    expect(smartInsertIndex(draft, "imprint_name")).toBe(2);
  });

  it("inserts imprint_name after cover when neither publisher nor favorite exists", () => {
    const draft = ["cover", "name"];
    expect(smartInsertIndex(draft, "imprint_name")).toBe(1);
  });

  it("inserts series_name after the other publishing groups", () => {
    const draft = ["cover", "publisher_name", "imprint_name", "name"];
    expect(smartInsertIndex(draft, "series_name")).toBe(3);
  });

  it("appends when the new key sorts after every existing key", () => {
    const draft = ["cover", "favorite", "name"];
    expect(smartInsertIndex(draft, "child_count")).toBe(3);
  });

  it("inserts at the head when the new key sorts before every existing key", () => {
    /* size precedes page_count in `_CATEGORIES.File` — keep it canonical. */
    const draft = ["size", "page_count"];
    expect(smartInsertIndex(draft, "cover")).toBe(0);
  });

  it("handles an empty draft", () => {
    expect(smartInsertIndex([], "favorite")).toBe(0);
  });

  it("handles a single-element draft (canonical-after)", () => {
    expect(smartInsertIndex(["cover"], "favorite")).toBe(1);
  });

  it("handles a single-element draft (canonical-before)", () => {
    expect(smartInsertIndex(["name"], "cover")).toBe(0);
  });
});

describe("smartInsertIndex — non-canonical drafts fall back to append", () => {
  it("appends when the user has rearranged columns out of canonical order", () => {
    /* name (rank 7) sitting before cover (rank 0) — user-sorted. */
    const draft = ["name", "cover", "publisher_name"];
    expect(smartInsertIndex(draft, "favorite")).toBe(draft.length);
  });

  it("appends when even one adjacent pair is reversed", () => {
    /* publisher (rank 2) before favorite (rank 1) — barely out of order. */
    const draft = ["cover", "publisher_name", "favorite", "name"];
    expect(smartInsertIndex(draft, "imprint_name")).toBe(draft.length);
  });
});

describe("smartInsertIndex — orphans (rank +Infinity)", () => {
  it("treats a draft ending in an orphan as still sorted", () => {
    /*
     * If a column lives outside `_CATEGORIES` (surfaced under
     * "Other"), it ranks at +∞ — a draft that ends with one is
     * still considered canonically sorted.
     */
    const draft = ["cover", "name", "__not_a_real_column__"];
    expect(smartInsertIndex(draft, "favorite")).toBe(1);
  });

  it("appends a new orphan to a canonical draft", () => {
    const draft = ["cover", "name"];
    expect(smartInsertIndex(draft, "__not_a_real_column__")).toBe(2);
  });

  it("appends when an orphan sits before a known key (out of order)", () => {
    const draft = ["cover", "__not_a_real_column__", "name"];
    expect(smartInsertIndex(draft, "favorite")).toBe(draft.length);
  });
});
