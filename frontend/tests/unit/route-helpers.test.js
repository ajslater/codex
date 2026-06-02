import { describe, expect, it } from "vitest";

import {
  collectionForRoute,
  normalizeParentIds,
  routeForCollection,
} from "@/route";

describe("route helpers", () => {
  it("passes an engine collection/pks straight to collection/parentIds", () => {
    expect(routeForCollection({ collection: "series", pks: "5,7" })).toEqual({
      collection: "series",
      parentIds: ["5", "7"],
    });
  });

  it("resolves the synthetic root collection to the publishers collection", () => {
    expect(routeForCollection({ collection: "root", pks: "0" })).toEqual({
      collection: "publishers",
      parentIds: [],
    });
  });

  it("round-trips publishers root back to the synthetic root collection", () => {
    expect(
      collectionForRoute({ collection: "publishers", parentIds: [] }),
    ).toEqual({
      collection: "root",
      pks: [],
    });
  });

  it("maps a parented collection straight through to the engine shape", () => {
    expect(
      collectionForRoute({ collection: "series", parentIds: ["5"] }),
    ).toEqual({
      collection: "series",
      pks: ["5"],
    });
  });

  it("normalizeParentIds drops 0, empties, and handles arrays", () => {
    expect(normalizeParentIds("0")).toEqual([]);
    expect(normalizeParentIds([5, 0, 7])).toEqual(["5", "7"]);
    expect(normalizeParentIds(undefined)).toEqual([]);
  });
});
