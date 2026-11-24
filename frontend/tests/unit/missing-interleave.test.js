/*
 * Missing issues go among the comics at their list positions; a long run
 * collapses into "N more missing".
 */
import { describe, expect, test } from "vitest";

import {
  interleaveMissing,
  RUN_LIMIT,
  RUN_SHOWN,
} from "@/components/browser/missing/interleave";

const comic = (pk, orderValue) => ({ pk, collection: "comics", orderValue });
const hole = (pk, position) => ({ pk, position, seriesName: `S${pk}` });

describe("interleaveMissing", () => {
  test("missing issues land between the comics", () => {
    const items = [comic(1, "1"), comic(2, "3")];
    const result = interleaveMissing(items, [hole(10, 0), hole(11, 2)]);
    expect(result.map((item) => item.pk)).toEqual([10, 1, 11, 2]);
    expect(result[0].missing).toBe(true);
  });

  test("reversed order mirrors it", () => {
    const items = [comic(2, "3"), comic(1, "1")];
    const result = interleaveMissing(items, [hole(11, 2), hole(10, 0)], {
      reverse: true,
    });
    expect(result.map((item) => item.pk)).toEqual([2, 11, 1, 10]);
  });

  test("table rows place by their position", () => {
    const rows = [
      { pk: 1, position: 1 },
      { pk: 2, position: 4 },
    ];
    const result = interleaveMissing(rows, [hole(10, 2)]);
    expect(result.map((item) => item.pk)).toEqual([1, 10, 2]);
  });

  test("no missing issues leaves the page as it was", () => {
    const items = [comic(1, "1")];
    expect(interleaveMissing(items, [])).toBe(items);
  });

  test("a long run collapses, and expands", () => {
    const holes = Array.from({ length: RUN_LIMIT + 2 }, (_, i) =>
      hole(100 + i, i + 1),
    );
    const items = [comic(1, "0")];
    const collapsed = interleaveMissing(items, holes);
    expect(collapsed).toHaveLength(1 + RUN_SHOWN + 1);
    const run = collapsed.at(-1);
    expect(run).toMatchObject({ missingRun: true, key: 100 });
    expect(run.count).toBe(holes.length - RUN_SHOWN);
    const expanded = interleaveMissing(items, holes, {
      expanded: new Set([100]),
    });
    expect(expanded).toHaveLength(1 + holes.length);
  });

  test("a run of exactly the limit stays open", () => {
    const holes = Array.from({ length: RUN_LIMIT }, (_, i) => hole(i, i + 1));
    expect(interleaveMissing([comic(1, "0")], holes)).toHaveLength(
      1 + RUN_LIMIT,
    );
  });
});
