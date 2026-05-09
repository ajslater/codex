/*
 * Pure-function tests for helpers exported from
 * ``stores/browser.js``. The helpers don't read or write the Pinia
 * store, so they're just imported and called directly — no
 * ``createTestingPinia`` required.
 *
 * ``filterShowGatedDefaults`` mirrors the backend's
 * ``default_columns_filtered`` logic: imprint_name / volume_name lead
 * the per-top-group default column tuples, but the user's show.i /
 * show.v flags gate them. If the user hides imprints from breadcrumb
 * navigation, they almost certainly don't want imprint_name leading
 * their default column set either.
 */
import { describe, expect, it } from "vitest";

import { filterShowGatedDefaults } from "@/stores/browser";

describe("filterShowGatedDefaults", () => {
  it("returns the input untouched when both show flags are on", () => {
    const cols = ["imprint_name", "volume_name", "issue", "page_count"];
    const out = filterShowGatedDefaults(cols, { i: true, v: true });
    expect(out).toStrictEqual(cols);
  });

  it("removes imprint_name when show.i is false", () => {
    const cols = ["imprint_name", "volume_name", "issue"];
    const out = filterShowGatedDefaults(cols, { i: false, v: true });
    expect(out).toStrictEqual(["volume_name", "issue"]);
  });

  it("removes volume_name when show.v is false", () => {
    const cols = ["imprint_name", "volume_name", "issue"];
    const out = filterShowGatedDefaults(cols, { i: true, v: false });
    expect(out).toStrictEqual(["imprint_name", "issue"]);
  });

  it("removes both gated columns when both flags are off", () => {
    const cols = ["imprint_name", "volume_name", "issue"];
    const out = filterShowGatedDefaults(cols, { i: false, v: false });
    expect(out).toStrictEqual(["issue"]);
  });

  it("preserves order of non-gated columns", () => {
    const cols = [
      "publisher_name",
      "imprint_name",
      "series_name",
      "volume_name",
      "issue",
    ];
    const out = filterShowGatedDefaults(cols, { i: false, v: false });
    expect(out).toStrictEqual(["publisher_name", "series_name", "issue"]);
  });

  it("only filters the leading gated columns by name (no positional logic)", () => {
    /*
     * The gate is name-based, not position-based — if a hypothetical
     * caller put imprint_name in the middle, it would still be
     * filtered out when show.i is off. (Defaults in practice always
     * lead with the gated names, but the helper doesn't enforce
     * that.)
     */
    const cols = ["issue", "imprint_name", "page_count"];
    const out = filterShowGatedDefaults(cols, { i: false, v: true });
    expect(out).toStrictEqual(["issue", "page_count"]);
  });

  it("returns an empty array unchanged", () => {
    expect(filterShowGatedDefaults([], { i: true, v: true })).toStrictEqual([]);
    expect(filterShowGatedDefaults([], { i: false, v: false })).toStrictEqual(
      [],
    );
  });

  it("returns [] for null / undefined cols (defensive)", () => {
    expect(filterShowGatedDefaults(null, { i: true, v: true })).toStrictEqual(
      [],
    );
    expect(
      filterShowGatedDefaults(undefined, { i: true, v: true }),
    ).toStrictEqual([]);
  });

  it("treats a missing show object as 'all flags off'", () => {
    /*
     * If the caller hands in null / undefined for show, the helper
     * treats every gated column as blocked. This is the conservative
     * fallback — better to omit columns the user might not want than
     * to surface ones they hid.
     */
    const cols = ["imprint_name", "volume_name", "issue"];
    expect(filterShowGatedDefaults(cols, null)).toStrictEqual(["issue"]);
    expect(filterShowGatedDefaults(cols, undefined)).toStrictEqual(["issue"]);
  });

  it("treats a non-object show value as 'all flags off'", () => {
    const cols = ["imprint_name", "volume_name", "issue"];
    expect(filterShowGatedDefaults(cols, "yes")).toStrictEqual(["issue"]);
    expect(filterShowGatedDefaults(cols, 1)).toStrictEqual(["issue"]);
  });

  it("does not mutate the input array", () => {
    const cols = ["imprint_name", "volume_name", "issue"];
    const snapshot = [...cols];
    filterShowGatedDefaults(cols, { i: false, v: false });
    expect(cols).toStrictEqual(snapshot);
  });

  it("returns the same reference when nothing is filtered", () => {
    /*
     * Small but useful contract: callers that compare with === to
     * detect 'changed?' shouldn't see false positives. When all
     * flags are on, the helper hands back the same array.
     */
    const cols = ["imprint_name", "volume_name", "issue"];
    const out = filterShowGatedDefaults(cols, { i: true, v: true });
    expect(out).toBe(cols);
  });
});
