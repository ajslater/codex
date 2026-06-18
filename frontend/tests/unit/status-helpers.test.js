import { describe, expect, it } from "vitest";

import {
  etaRemaining,
  retryRemaining,
} from "@/components/admin/status-helpers";

const base = new Date("2026-06-12T00:00:00.000Z").getTime();
const iso = (offsetSeconds) =>
  new Date(base + offsetSeconds * 1000).toISOString();

describe("retryRemaining", () => {
  it("is empty when there's no retryAt", () => {
    expect(retryRemaining({}, base)).toBe("");
  });

  it("counts down to retryAt formatted as m:ss", () => {
    // retry 570s out -> 9:30
    expect(retryRemaining({ retryAt: iso(570) }, base)).toBe(
      "retrying in 9:30",
    );
  });

  it("formats sub-minute remainders as plain seconds", () => {
    expect(retryRemaining({ retryAt: iso(15) }, base)).toBe("retrying in 15s");
  });

  it("shows 'retrying now…' once the target passes", () => {
    expect(retryRemaining({ retryAt: iso(-5) }, base)).toBe("retrying now…");
  });
});

describe("etaRemaining", () => {
  it("is empty when the status isn't active", () => {
    expect(etaRemaining({ eta: iso(300) }, base)).toBe("");
  });

  it("is empty when there's no eta", () => {
    expect(etaRemaining({ active: iso(0) }, base)).toBe("");
  });

  it("renders a coarse '~Xm Ys left' countdown", () => {
    // 6m 30s out
    expect(etaRemaining({ active: iso(0), eta: iso(390) }, base)).toBe(
      "~6m 30s left",
    );
  });

  it("renders hours for long estimates", () => {
    // 1h 5m out
    expect(etaRemaining({ active: iso(0), eta: iso(3900) }, base)).toBe(
      "~1h 5m left",
    );
  });

  it("shows 'finishing…' once eta passes", () => {
    expect(etaRemaining({ active: iso(0), eta: iso(-10) }, base)).toBe(
      "finishing…",
    );
  });
});
