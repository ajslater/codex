/*
 * Tests for the tag edit panel's Alternate Series section.
 *
 * The metadata endpoint ships each reprint's flat codex columns
 * ({pk, name, seriesName, volumeNumber, issue, language, url}) alongside the
 * composed chip `name`, so the editor seeds its rows from the parts instead
 * of parsing the label back apart. On save the parts have to be re-nested
 * into comicbox's reprint shape ({series: {name}, volume: {number}, issue,
 * language}), and clearing the section has to travel as the "reprints"
 * delete key — a patch can only add or replace.
 *
 * Volume and language are MetronInfo-only: ComicInfo's AlternateSeries /
 * AlternateNumber / AlternateCount carry neither.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import vuetify from "@/plugins/vuetify";

const DISABLED_TIP = "Not supported by selected metadata formats";

// Absent parts arrive as the model's own empty defaults: "" for the
// strings, null for the volume number.
const SHAPED_REPRINTS = Object.freeze([
  {
    pk: 7,
    name: "Kapitän Wissenschaft (de)",
    seriesName: "Kapitän Wissenschaft",
    volumeNumber: null,
    issue: "",
    language: "de",
  },
  {
    pk: 8,
    name: "Capitan Sciencia v1 #3",
    seriesName: "Capitan Sciencia",
    volumeNumber: 1,
    issue: "3",
    language: "",
  },
]);

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

function findButton(wrapper, label) {
  return wrapper.findAll("button").find((b) => b.text().includes(label));
}

describe("EditPanel alternate series rows", () => {
  test("seeds one row per reprint from the flat columns", async () => {
    const wrapper = await mountPanel({ md: { reprints: SHAPED_REPRINTS } });

    expect(wrapper.vm.reprints).toStrictEqual([
      {
        series_name: "Kapitän Wissenschaft",
        volume: "",
        issue: "",
        language: "de",
      },
      {
        series_name: "Capitan Sciencia",
        volume: "1",
        issue: "3",
        language: null,
      },
    ]);
    expect(wrapper.vm.hasChanges).toBe(false);
  });

  test("leaves the rows empty when the comic has no reprints", async () => {
    const wrapper = await mountPanel({ md: { reprints: [] } });
    expect(wrapper.vm.reprints).toStrictEqual([]);
  });

  test("the add button appends a blank row", async () => {
    const wrapper = await mountPanel();
    await findButton(wrapper, "Add Alternate Series").trigger("click");

    expect(wrapper.vm.reprints).toStrictEqual([
      { series_name: "", volume: "", issue: "", language: null },
    ]);
  });
});

describe("EditPanel alternate series patch", () => {
  test("re-nests the parts into comicbox reprints", async () => {
    const wrapper = await mountPanel({ md: { reprints: SHAPED_REPRINTS } });
    wrapper.vm.reprints[0].issue = "1";
    await flushPromises();

    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(patch).toStrictEqual({
      reprints: [
        {
          series: { name: "Kapitän Wissenschaft" },
          issue: "1",
          language: "de",
        },
        {
          series: { name: "Capitan Sciencia" },
          volume: { number: 1 },
          issue: "3",
        },
      ],
    });
    expect(deleteKeys).toStrictEqual([]);
  });

  test("an untouched section stays out of the patch entirely", async () => {
    const wrapper = await mountPanel({ md: { reprints: SHAPED_REPRINTS } });
    const { patch, deleteKeys } = wrapper.vm.buildPatch();

    expect(patch).not.toHaveProperty("reprints");
    expect(deleteKeys).not.toContain("reprints");
  });

  test("a newly added row travels with only the parts it carries", async () => {
    const wrapper = await mountPanel();
    wrapper.vm.reprints.push({
      series_name: "Capitaine Science",
      volume: "",
      issue: "",
      language: null,
    });
    await flushPromises();

    const { patch } = wrapper.vm.buildPatch();
    expect(patch.reprints).toStrictEqual([
      { series: { name: "Capitaine Science" } },
    ]);
  });

  test("removing a row drops it from the patch", async () => {
    const wrapper = await mountPanel({ md: { reprints: SHAPED_REPRINTS } });
    wrapper.vm.reprints.splice(0, 1);
    await flushPromises();

    const { patch } = wrapper.vm.buildPatch();
    expect(patch.reprints).toHaveLength(1);
    expect(patch.reprints[0].series.name).toBe("Capitan Sciencia");
  });

  test("a row with no series name names nothing and is dropped", async () => {
    const wrapper = await mountPanel();
    wrapper.vm.reprints.push({
      series_name: "",
      volume: "2",
      issue: "",
      language: "fr",
    });
    await flushPromises();

    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(patch).not.toHaveProperty("reprints");
    expect(deleteKeys).toStrictEqual(["reprints"]);
  });

  test("clearing the section deletes the comicbox reprints key", async () => {
    const wrapper = await mountPanel({ md: { reprints: SHAPED_REPRINTS } });
    wrapper.vm.clearField("reprints");
    await flushPromises();

    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(wrapper.vm.reprints).toStrictEqual([]);
    expect(deleteKeys).toStrictEqual(["reprints"]);
    expect(patch).not.toHaveProperty("reprints");
  });

  test("emptying every row also deletes rather than patching nothing", async () => {
    const wrapper = await mountPanel({ md: { reprints: SHAPED_REPRINTS } });
    wrapper.vm.reprints = [];
    await flushPromises();

    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toStrictEqual(["reprints"]);
    expect(patch).not.toHaveProperty("reprints");
  });
});

describe("EditPanel alternate series format support", () => {
  test("ComicInfo disables the MetronInfo-only volume and language", async () => {
    const wrapper = await mountPanel({
      formats: ["COMIC_INFO"],
      md: { reprints: SHAPED_REPRINTS },
    });
    const volume = wrapper
      .findAll("input")
      .find((i) => i.element.value === "1");

    expect(volume.element.disabled).toBe(true);
    expect(volume.element.closest("td").getAttribute("title")).toBe(
      DISABLED_TIP,
    );
    expect(wrapper.vm.isFieldDisabled("reprint_language")).toBe(true);
    // The series name and issue do persist to ComicInfo's Alternates.
    expect(wrapper.vm.isFieldDisabled("reprints")).toBe(false);
  });

  test("MetronInfo enables every part", async () => {
    const wrapper = await mountPanel({
      formats: ["METRON_INFO"],
      md: { reprints: SHAPED_REPRINTS },
    });
    const btn = findButton(wrapper, "Add Alternate Series");

    expect(btn.element.disabled).toBe(false);
    expect(wrapper.vm.isFieldDisabled("reprint_volume")).toBe(false);
    expect(wrapper.vm.isFieldDisabled("reprint_language")).toBe(false);
  });
});

export default {};
