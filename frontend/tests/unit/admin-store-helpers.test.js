/*
 * The admin store's sticky-cache test. Every admin load skips its request
 * while ``isFresh`` holds for the data's last-loaded stamp.
 */
import { describe, expect, it, vi } from "vitest";

import { isFresh } from "@/stores/admin";

const NOW = 1_000_000;
const TTL = 5000;

describe("isFresh", () => {
  it.each([
    ["never loaded", 0],
    ["no stamp", undefined],
  ])("is stale when %s", (_label, last) => {
    expect(isFresh(last, TTL, NOW)).toBe(false);
  });

  it.each([
    ["just loaded", 0, true],
    ["inside the window", TTL - 1, true],
    ["exactly one window old", TTL, false],
    ["past the window", TTL + 1, false],
  ])("%s: %s ms old is fresh: %s", (_label, age, fresh) => {
    expect(isFresh(NOW - age, TTL, NOW)).toBe(fresh);
  });

  it("never expires with an infinite window", () => {
    expect(isFresh(1, Infinity, NOW)).toBe(true);
  });

  it("defaults to a five second window from now", () => {
    vi.useFakeTimers({ now: NOW });
    try {
      expect(isFresh(NOW - TTL + 1)).toBe(true);
      expect(isFresh(NOW - TTL)).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("treats an undefined window as the default", () => {
    expect(isFresh(NOW - 1, undefined, NOW)).toBe(true);
    expect(isFresh(NOW - TTL, undefined, NOW)).toBe(false);
  });
});

export default {};
