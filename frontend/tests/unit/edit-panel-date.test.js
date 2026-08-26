/*
 * Tests for the tag edit panel's publish date parts.
 *
 * Behavior locked in here:
 *   - buildPatch assembles the nested comicbox shape
 *     {date: {year, month, day}} whenever any part changed.
 *   - Update mode replaces the key wholesale, so every surviving part rides
 *     along on any change, a cleared part drops out of the replacement, and
 *     only a fully empty date needs a comicbox delete key.
 *   - Partial dates are legitimate: a comic may carry only a year.
 *   - The parts clear to null rather than "", and both write formats
 *     support them.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import vuetify from "@/plugins/vuetify";

const FULL_DATE_MD = { year: 1987, month: 3, day: 12 };

async function mountPanel({ formats = ["COMIC_INFO"], md = {} } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      metadata: { md },
      admin: { taggingDefaults: { defaultFormats: formats } },
      browser: { settings: { twentyFourHourTime: false } },
    },
  });
  const wrapper = mount(EditPanel, {
    props: { book: { pk: 1, collection: "comics", ids: [1] } },
    global: { plugins: [pinia, vuetify] },
  });
  await flushPromises();
  return wrapper;
}

async function setParts(wrapper, parts) {
  for (const [part, value] of Object.entries(parts)) {
    wrapper.vm.patch[part] = value;
    wrapper.vm.onFieldInput(part);
  }
  await flushPromises();
}

describe("EditPanel — publish date", () => {
  test("each part renders its own labeled input", async () => {
    const wrapper = await mountPanel({ md: FULL_DATE_MD });
    const labels = wrapper.findAll("label").map((el) => el.text());
    expect(labels).toEqual(expect.arrayContaining(["Year", "Month", "Day"]));
    // The seeded date reaches the inputs the user actually types into.
    const values = wrapper
      .findAll("input")
      .map((el) => el.element.value)
      .filter(Boolean);
    expect(values).toEqual(expect.arrayContaining(["1987", "3", "12"]));
  });

  test("the parts build the nested comicbox shape", async () => {
    const wrapper = await mountPanel();
    await setParts(wrapper, { year: 1987, month: 3, day: 12 });
    expect(wrapper.vm.buildPatch().patch.date).toEqual({
      year: 1987,
      month: 3,
      day: 12,
    });
  });

  test("changing one part still sends the others", async () => {
    const wrapper = await mountPanel({ md: FULL_DATE_MD });
    await setParts(wrapper, { month: 6 });
    expect(wrapper.vm.buildPatch().patch.date).toEqual({
      year: 1987,
      month: 6,
      day: 12,
    });
  });

  test("a year alone is a legitimate date", async () => {
    const wrapper = await mountPanel();
    await setParts(wrapper, { year: 1987 });
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(patch.date).toEqual({ year: 1987 });
    expect(deleteKeys).not.toContain("date");
  });

  test("clearing one part drops it from the replacement", async () => {
    const wrapper = await mountPanel({ md: FULL_DATE_MD });
    wrapper.vm.toggleClear("day");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(patch.date).toEqual({ year: 1987, month: 3 });
    expect(deleteKeys).not.toContain("date");
    expect(deleteKeys).not.toContain("date.day");
  });

  test("clearing every part deletes the whole date", async () => {
    const wrapper = await mountPanel({ md: FULL_DATE_MD });
    for (const part of ["year", "month", "day"]) {
      wrapper.vm.toggleClear(part);
    }
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("date");
    expect(patch).not.toHaveProperty("date");
  });

  test("blanking the only part deletes the whole date", async () => {
    const wrapper = await mountPanel({ md: { year: 1987 } });
    await setParts(wrapper, { year: "" });
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("date");
    expect(patch).not.toHaveProperty("date");
  });

  test("an untouched date is never written", async () => {
    const wrapper = await mountPanel({ md: FULL_DATE_MD });
    wrapper.vm.patch.summary = "Edited elsewhere";
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(patch).not.toHaveProperty("date");
    expect(deleteKeys).not.toContain("date");
  });

  test("the parts clear to null rather than an empty string", async () => {
    const wrapper = await mountPanel({ md: FULL_DATE_MD });
    wrapper.vm.toggleClear("year");
    await flushPromises();
    expect(wrapper.vm.patch.year).toBeNull();
  });

  test("both write formats support the parts", async () => {
    for (const formats of [
      ["COMIC_INFO"],
      ["METRON_INFO"],
      ["COMIC_INFO", "METRON_INFO"],
    ]) {
      const wrapper = await mountPanel({ formats });
      for (const part of ["year", "month", "day"]) {
        expect(wrapper.vm.isFieldDisabled(part)).toBe(false);
      }
    }
  });

  test("the rules bound each part", async () => {
    const wrapper = await mountPanel();
    const check = (rules, value) => rules.map((rule) => rule(value));
    expect(check(wrapper.vm.monthRules, 13)).toContain("Must be 1–12");
    expect(check(wrapper.vm.dayRules, 32)).toContain("Must be 1–31");
    expect(check(wrapper.vm.yearRules, 0)).toContain("Must be 1–9999");
    expect(check(wrapper.vm.yearRules, 10_000)).toContain("Must be 1–9999");
    for (const empty of [null, "", undefined]) {
      expect(check(wrapper.vm.yearRules, empty)).toEqual([true]);
    }
    expect(check(wrapper.vm.monthRules, 12)).toEqual([true]);
    expect(check(wrapper.vm.dayRules, 31)).toEqual([true]);
    expect(check(wrapper.vm.yearRules, 1987)).toEqual([true]);
  });

  test("retyping a cleared part revives it", async () => {
    // Nothing else un-clears a field, so without the input handler the typed
    // value is shown but dropped from the write.
    const wrapper = await mountPanel({ md: FULL_DATE_MD });
    wrapper.vm.toggleClear("year");
    await flushPromises();
    await setParts(wrapper, { year: 1990 });
    expect(wrapper.vm.isCleared("year")).toBe(false);
    expect(wrapper.vm.buildPatch().patch.date).toEqual({
      year: 1990,
      month: 3,
      day: 12,
    });
  });

  test("out-of-range parts are bounded rather than written raw", async () => {
    // Save is not gated on the rules, and comicbox writes any year it is
    // handed into a column that only takes positive small ints.
    const wrapper = await mountPanel();
    await setParts(wrapper, { year: 99_999, month: 13, day: 45 });
    expect(wrapper.vm.buildPatch().patch.date).toEqual({
      year: 9999,
      month: 12,
      day: 31,
    });
    const negative = await mountPanel();
    await setParts(negative, { year: -5 });
    expect(negative.vm.buildPatch().patch.date).toEqual({ year: 1 });
  });

  test("a fractional part rounds instead of vanishing", async () => {
    const wrapper = await mountPanel({ md: FULL_DATE_MD });
    await setParts(wrapper, { year: 1987.6 });
    expect(wrapper.vm.buildPatch().patch.date.year).toBe(1988);
  });
});
