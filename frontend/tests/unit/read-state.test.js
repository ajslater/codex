/*
 * Pure-function tests for ``read-state.js``. No store and no mounting — the
 * module only reads ``finished``, ``progress`` and ``collection`` off a card
 * or metadata payload.
 *
 * The case that matters most is ``{finished: true, progress: 0}``: "Mark Read"
 * from the card menu and from select-many both PATCH ``{finished}`` alone, so
 * the bookmark page stays 0. Before this module the card derived its bar from
 * ``progress`` first, which rendered nothing at all and made a comic that had
 * been marked read pixel-identical to one never opened — the defect in
 * issue 856.
 */
import { describe, expect, it } from "vitest";

import {
  getReadFillPercent,
  getReadState,
  getReadStateLabel,
  READ_STATE,
} from "@/read-state";

const comic = (finished, progress) => ({
  collection: "comics",
  finished,
  progress,
});
const folder = (finished, progress) => ({
  collection: "folders",
  finished,
  progress,
});

describe("getReadState", () => {
  it("reads finished before progress", () => {
    // The regression test for issue 856.
    expect(getReadState(comic(true, 0))).toBe(READ_STATE.FINISHED);
  });

  it("treats a fully read but unmarked comic as still reading", () => {
    expect(getReadState(comic(false, 100))).toBe(READ_STATE.READING);
  });

  it("treats an untouched comic as unread", () => {
    expect(getReadState(comic(false, 0))).toBe(READ_STATE.UNREAD);
  });

  it("treats a part read comic as reading", () => {
    expect(getReadState(comic(false, 56))).toBe(READ_STATE.READING);
  });

  it("treats a mixed collection as reading", () => {
    // ``null`` is the collection tri-state for "some children finished".
    expect(getReadState(folder(null, 35))).toBe(READ_STATE.READING);
  });

  it("treats a touched but nothing-finished collection as reading", () => {
    expect(getReadState(folder(false, 4))).toBe(READ_STATE.READING);
  });

  it("treats an untouched collection as unread", () => {
    expect(getReadState(folder(false, 0))).toBe(READ_STATE.UNREAD);
  });

  it("treats a fully read collection as finished", () => {
    expect(getReadState(folder(true, 100))).toBe(READ_STATE.FINISHED);
  });
});

describe("getReadFillPercent", () => {
  it("leaves a marked-read comic at zero", () => {
    // Thickness carries "finished", so the fill stays honest: a bare thick
    // track is how the card says "read, never opened".
    expect(getReadFillPercent(comic(true, 0))).toBe(0);
  });

  it("keeps a finished comic's real position", () => {
    expect(getReadFillPercent(comic(true, 12))).toBe(12);
  });

  it("floors a barely started comic so it paints something", () => {
    expect(getReadFillPercent(comic(false, 0.33))).toBe(6);
  });

  it("does not floor the finished state", () => {
    expect(getReadFillPercent(comic(true, 0.33))).toBe(0.33);
  });

  it("paints nothing when unread", () => {
    expect(getReadFillPercent(comic(false, 0))).toBe(0);
  });

  it("allows a part read comic to reach full width", () => {
    // No ceiling: thickness and the caption colour already separate this
    // from finished, so the length is allowed to be truthful.
    expect(getReadFillPercent(comic(false, 100))).toBe(100);
  });

  it("clamps out-of-range progress", () => {
    expect(getReadFillPercent(comic(false, 140))).toBe(100);
  });

  it("survives a missing progress", () => {
    expect(getReadFillPercent(comic(false, undefined))).toBe(0);
  });

  it("uses the collection percentage for a mixed collection", () => {
    expect(getReadFillPercent(folder(null, 35))).toBe(35);
  });
});

describe("getReadStateLabel", () => {
  it("labels comics and collections differently", () => {
    expect(getReadStateLabel(comic(true, 100))).toBe("read");
    expect(getReadStateLabel(folder(true, 100))).toBe("all read");
    expect(getReadStateLabel(comic(false, 0))).toBe("unread");
    expect(getReadStateLabel(folder(false, 0))).toBe("none read");
    expect(getReadStateLabel(folder(null, 35))).toBe("partly read");
  });

  it("rounds a comic's percentage", () => {
    expect(getReadStateLabel(comic(false, 55.56))).toBe("56% read");
  });

  it("announces a marked-read comic as read, not as 0%", () => {
    expect(getReadStateLabel(comic(true, 0))).toBe("read");
  });

  it("never claims 100% while the comic is still being read", () => {
    // Page 249 of 251 rounds to 100, but the bar beside it is still the
    // thin READING style and ``finished`` is false.
    expect(getReadStateLabel(comic(false, 99.6))).toBe("99% read");
  });

  it("never claims 0% while the comic is being read", () => {
    // Page 1 of 251 rounds to 0, but the bar already paints its floor.
    expect(getReadStateLabel(comic(false, 0.4))).toBe("1% read");
  });

  it("leaves a finished comic's label alone", () => {
    expect(getReadStateLabel(comic(true, 99.6))).toBe("read");
  });
});
