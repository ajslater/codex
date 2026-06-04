import { describe, expect, it } from "vitest";

import {
  browserRouteParams,
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

  describe("browserRouteParams (never an array — vue-router throws on that)", () => {
    it("joins an array parentIds into the route's string token", () => {
      expect(
        browserRouteParams({ collection: "series", parentIds: ["5", "7"] }),
      ).toEqual({ collection: "series", parentIds: "5,7" });
    });

    it("omits parentIds for an empty array (the reader close-route crash)", () => {
      // LAST_ROUTE injects parentIds: []; passing it through verbatim made the
      // reader's Close Book button blow up the whole render.
      expect(
        browserRouteParams({ collection: "publishers", parentIds: [] }),
      ).toEqual({ collection: "publishers" });
    });

    it("accepts the engine pks shape and a comma string alike", () => {
      expect(browserRouteParams({ collection: "folders", pks: [3] })).toEqual({
        collection: "folders",
        parentIds: "3",
      });
      expect(
        browserRouteParams({ collection: "series", parentIds: "5,7" }),
      ).toEqual({ collection: "series", parentIds: "5,7" });
    });
  });
});
