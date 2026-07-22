/*
 * Tests for the credential-test result chip on the admin Tagging tab.
 *
 * Behavior locked in here:
 *   - ok without rate limits renders exactly "Connected".
 *   - a failure renders the error text (or "Failed" when blank).
 *   - a successful Metron check appends the account's live rate limits
 *     (burst cap + sustained daily budget) that mokkari 4 reads off the
 *     validation response's X-RateLimit-* headers.
 *   - partial windows degrade gracefully; null rateLimits (Comic Vine
 *     results) stay plain "Connected".
 */
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ValidationChip from "@/components/admin/tabs/tagging-validation-chip.vue";
import { NUMBER_FORMAT } from "@/datetime";
import vuetify from "@/plugins/vuetify";

function mountChip(result) {
  return mount(ValidationChip, {
    props: { result },
    global: { plugins: [vuetify] },
  });
}

const fmt = (n) => NUMBER_FORMAT.format(n);

describe("tagging validation chip", () => {
  test("ok without rate limits shows plain Connected", () => {
    const wrapper = mountChip({ ok: true });
    expect(wrapper.text()).toBe("Connected");
  });

  test("failure shows the error text", () => {
    const wrapper = mountChip({ ok: false, error: "bad password" });
    expect(wrapper.text()).toBe("bad password");
    expect(wrapper.text()).not.toContain("Connected");
  });

  test("failure without an error message falls back to Failed", () => {
    const wrapper = mountChip({ ok: false });
    expect(wrapper.text()).toBe("Failed");
  });

  test("full rate limits append burst cap and daily budget", () => {
    const wrapper = mountChip({
      ok: true,
      rateLimits: {
        burst: { limit: 20, remaining: 19 },
        sustained: { limit: 25_000, remaining: 24_987 },
      },
    });
    expect(wrapper.text()).toBe(
      `Connected · 20/min · ${fmt(24_987)} of ${fmt(25_000)} left today`,
    );
  });

  test("sustained limit alone renders as a per-day cap", () => {
    const wrapper = mountChip({
      ok: true,
      rateLimits: { sustained: { limit: 5000 } },
    });
    expect(wrapper.text()).toBe(`Connected · ${fmt(5000)}/day`);
    expect(wrapper.text()).not.toContain("/min");
  });

  test("zero remaining still renders (exhausted budget is the interesting case)", () => {
    const wrapper = mountChip({
      ok: true,
      rateLimits: {
        burst: { limit: 20 },
        sustained: { limit: 5000, remaining: 0 },
      },
    });
    expect(wrapper.text()).toBe(
      `Connected · 20/min · 0 of ${fmt(5000)} left today`,
    );
  });

  test("null rateLimits (Comic Vine results) stays plain Connected", () => {
    const wrapper = mountChip({ ok: true, rateLimits: null });
    expect(wrapper.text()).toBe("Connected");
  });
});
