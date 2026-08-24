/*
 * Tests for tag edit panel fields that only some write formats carry.
 *
 * Behavior locked in here:
 *   - The alternative issue's number + suffix build the same nested comicbox
 *     issue shape as the issue proper, replaced wholesale on any change.
 *   - Collection title is a plain string, cleared through a delete key.
 *   - Country rides the technical select path alongside language, storing
 *     the two-letter code the Country model names.
 *   - Per-format enablement: the alternative issue and collection title are
 *     METRON_INFO-only; country is COMIC_INFO-only.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import vuetify from "@/plugins/vuetify";

async function mountPanel({ formats = ["METRON_INFO"], md = {} } = {}) {
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

async function setField(wrapper, field, value) {
  wrapper.vm.patch[field] = value;
  wrapper.vm.onFieldInput(field);
  await flushPromises();
}

describe("EditPanel — alternative issue", () => {
  test("the new fields render their own labeled inputs", async () => {
    const wrapper = await mountPanel({
      formats: ["COMIC_INFO", "METRON_INFO"],
    });
    const labels = wrapper.findAll("label").map((el) => el.text());
    expect(labels).toEqual(
      expect.arrayContaining([
        "Alternative Issue Number",
        "Alternative Issue Suffix",
        "Collection Title",
        "Country",
      ]),
    );
  });

  test("number and suffix build the nested comicbox shape", async () => {
    const wrapper = await mountPanel();
    await setField(wrapper, "alternative_issue_number", "5");
    await setField(wrapper, "alternative_issue_suffix", "AU");
    expect(wrapper.vm.buildPatch().patch.alternative_issue).toEqual({
      number: 5,
      suffix: "AU",
    });
  });

  test("changing the suffix still sends the current number", async () => {
    const wrapper = await mountPanel({
      md: { alternativeIssueNumber: "5", alternativeIssueSuffix: "AU" },
    });
    await setField(wrapper, "alternative_issue_suffix", "DF");
    expect(wrapper.vm.buildPatch().patch.alternative_issue).toEqual({
      number: 5,
      suffix: "DF",
    });
  });

  test("clearing both parts deletes the whole key", async () => {
    const wrapper = await mountPanel({
      md: { alternativeIssueNumber: "5", alternativeIssueSuffix: "AU" },
    });
    wrapper.vm.toggleClear("alternative_issue_number");
    wrapper.vm.toggleClear("alternative_issue_suffix");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("alternative_issue");
    expect(patch).not.toHaveProperty("alternative_issue");
  });

  test("it never disturbs the issue proper", async () => {
    const wrapper = await mountPanel({
      md: { issueNumber: "1", alternativeIssueNumber: "5" },
    });
    await setField(wrapper, "alternative_issue_number", "6");
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(patch.alternative_issue).toEqual({ number: 6 });
    expect(patch).not.toHaveProperty("issue");
    expect(deleteKeys).not.toContain("issue");
  });

  test("it is METRON_INFO-only", async () => {
    const metron = await mountPanel({ formats: ["METRON_INFO"] });
    const comicInfo = await mountPanel({ formats: ["COMIC_INFO"] });
    for (const field of [
      "alternative_issue_number",
      "alternative_issue_suffix",
    ]) {
      expect(metron.vm.isFieldDisabled(field)).toBe(false);
      expect(comicInfo.vm.isFieldDisabled(field)).toBe(true);
    }
  });
});

describe("EditPanel — collection title", () => {
  test("it writes as a plain string", async () => {
    const wrapper = await mountPanel();
    await setField(wrapper, "collection_title", "The Dark Phoenix Saga");
    expect(wrapper.vm.buildPatch().patch.collection_title).toBe(
      "The Dark Phoenix Saga",
    );
  });

  test("clearing it emits a delete key", async () => {
    const wrapper = await mountPanel({
      md: { collectionTitle: "The Dark Phoenix Saga" },
    });
    wrapper.vm.toggleClear("collection_title");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("collection_title");
    expect(patch).not.toHaveProperty("collection_title");
  });

  test("it is METRON_INFO-only", async () => {
    const metron = await mountPanel({ formats: ["METRON_INFO"] });
    const comicInfo = await mountPanel({ formats: ["COMIC_INFO"] });
    expect(metron.vm.isFieldDisabled("collection_title")).toBe(false);
    expect(comicInfo.vm.isFieldDisabled("collection_title")).toBe(true);
  });
});

describe("EditPanel — country", () => {
  test("it writes the two-letter code", async () => {
    const wrapper = await mountPanel({ formats: ["COMIC_INFO"] });
    await setField(wrapper, "country", "US");
    expect(wrapper.vm.buildPatch().patch.country).toBe("US");
  });

  test("it seeds the code behind the name the API serializes", async () => {
    // CountryField maps alpha-2 to the long English name on the way out, but
    // the choices are keyed by the code comicbox writes.
    const wrapper = await mountPanel({
      formats: ["COMIC_INFO"],
      md: { country: { name: "Japan" }, language: { name: "English" } },
    });
    expect(wrapper.vm.patch.country).toBe("JP");
    expect(wrapper.vm.patch.language).toBe("en");
  });

  test("a seeded country is not itself an edit", async () => {
    // A value matching no item leaves the select unselected, and re-picking
    // it would flip the panel dirty for a no-op.
    const wrapper = await mountPanel({
      formats: ["COMIC_INFO"],
      md: { country: { name: "Japan" } },
    });
    expect([...wrapper.vm.changedFields]).toEqual([]);
    const codes = new Set(wrapper.vm.countryChoices.map((c) => c.value));
    expect(codes.has(wrapper.vm.patch.country)).toBe(true);
  });

  test("clearing it emits a delete key", async () => {
    const wrapper = await mountPanel({
      formats: ["COMIC_INFO"],
      md: { country: { name: "United States" } },
    });
    wrapper.vm.toggleClear("country");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("country");
    expect(patch).not.toHaveProperty("country");
  });

  test("its choices are the ISO country list", async () => {
    const wrapper = await mountPanel({ formats: ["COMIC_INFO"] });
    expect(wrapper.vm.countryChoices.length).toBeGreaterThan(200);
    expect(wrapper.vm.countryChoices).toContainEqual({
      title: "Japan",
      value: "JP",
    });
  });

  test("it is COMIC_INFO-only", async () => {
    const comicInfo = await mountPanel({ formats: ["COMIC_INFO"] });
    const metron = await mountPanel({ formats: ["METRON_INFO"] });
    expect(comicInfo.vm.isFieldDisabled("country")).toBe(false);
    expect(metron.vm.isFieldDisabled("country")).toBe(true);
  });
});
