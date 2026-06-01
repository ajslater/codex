import { describe, expect, it } from "vitest";

import { groupForRoute, normalizeParentIds, routeForGroup } from "@/route";

describe("route helpers", () => {
  it("maps legacy group/pks to v4 collection/parentIds", () => {
    expect(routeForGroup({ group: "s", pks: "5,7" })).toEqual({
      collection: "series",
      parentIds: ["5", "7"],
    });
  });

  it("drops the dummy 0 to an empty parentIds (root)", () => {
    expect(routeForGroup({ group: "r", pks: "0" })).toEqual({
      collection: "publishers",
      parentIds: [],
    });
  });

  it("round-trips publishers root back to the synthetic root group", () => {
    expect(groupForRoute({ collection: "publishers", parentIds: [] })).toEqual({
      group: "root",
      pks: [],
    });
  });

  it("maps a parented collection straight through to its group", () => {
    expect(groupForRoute({ collection: "series", parentIds: ["5"] })).toEqual({
      group: "series",
      pks: ["5"],
    });
  });

  it("normalizeParentIds drops 0, empties, and handles arrays", () => {
    expect(normalizeParentIds("0")).toEqual([]);
    expect(normalizeParentIds([5, 0, 7])).toEqual(["5", "7"]);
    expect(normalizeParentIds(undefined)).toEqual([]);
  });
});
