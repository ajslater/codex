/*
 * Tests for the tag edit panel's collection inputs (publisher / imprint /
 * series / volume) as combo boxes.
 *
 * Behavior locked in here:
 *   - When the opened group spans MORE THAN ONE distinct value for a collection
 *     (e.g. case-variant publishers "Marvel" + "marvel"), the field starts
 *     BLANK and the dropdown offers both names. Picking any option — including
 *     the first/canonical one — registers as a change and enables Save, so the
 *     chosen value can be written to every selected comic to normalize them.
 *   - When the group has a SINGLE value, the field is pre-filled with that value
 *     and shows no "multiple" placeholder — i.e. ordinary editing is unchanged.
 *   - The four collection inputs render as comboboxes (freeform + dropdown).
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import vuetify from "@/plugins/vuetify";

const MULTI_PLACEHOLDER = "Multiple — select one to apply to all";

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
  // mounted() seeds the patch from metadata and captures the orig snapshot;
  // both are reactive, so let the DOM flush before asserting.
  await flushPromises();
  return wrapper;
}

describe("EditPanel — ambiguous (duplicate) collections", () => {
  const DUP_PUBLISHER = {
    publisherList: [
      { ids: [1], name: "Marvel" },
      { ids: [2], name: "marvel" },
    ],
  };

  test("a duplicated publisher starts blank with no pending change", async () => {
    const wrapper = await mountPanel({ md: DUP_PUBLISHER });
    expect(wrapper.vm.patch.publisher).toBe("");
    expect(wrapper.vm.hasChanges).toBe(false);
  });

  test("the dropdown offers each distinct group value", async () => {
    const wrapper = await mountPanel({ md: DUP_PUBLISHER });
    expect(wrapper.vm.collectionOptions("publisher")).toEqual([
      "Marvel",
      "marvel",
    ]);
    expect(wrapper.vm.collectionPlaceholder("publisher")).toBe(
      MULTI_PLACEHOLDER,
    );
  });

  test("picking the first/canonical value enables Save and writes it", async () => {
    const wrapper = await mountPanel({ md: DUP_PUBLISHER });
    // Re-selecting the value already shown in the group is the case that was
    // impossible with a plain text field — it must now count as a change.
    wrapper.vm.patch.publisher = "Marvel";
    await flushPromises();
    expect(wrapper.vm.hasChanges).toBe(true);
    expect(wrapper.vm.buildPatch().publisher).toEqual({ name: "Marvel" });
  });

  test("an untouched ambiguous field is never written", async () => {
    // Editing something else on a multi-publisher group must not clobber the
    // publishers: a blank, untouched collection field stays out of the patch.
    const wrapper = await mountPanel({ md: DUP_PUBLISHER });
    wrapper.vm.patch.summary = "edited";
    await flushPromises();
    expect(wrapper.vm.hasChanges).toBe(true);
    expect(wrapper.vm.buildPatch().publisher).toBeUndefined();
  });

  test("numeric volumes are deduped and blanked when ambiguous", async () => {
    const wrapper = await mountPanel({
      md: {
        volumeList: [
          { ids: [1], name: 1 },
          { ids: [2], name: 2 },
        ],
      },
    });
    expect(wrapper.vm.collectionOptions("volume")).toEqual([1, 2]);
    expect(wrapper.vm.patch.volume).toBe("");
    expect(wrapper.vm.hasChanges).toBe(false);
  });
});

describe("EditPanel — a named value mixed with the unnamed (no-collection) state", () => {
  // Some comics carry an imprint, others have none. The backend lists the
  // default unnamed Imprint as a {name: ""} row alongside the named one, so the
  // group has no common value and the field must blank — letting the user pick
  // the named imprint and apply it to every comic. Regression: the empty row
  // was dropped before counting, so the field pre-filled the lone named value
  // and re-selecting it registered no change.
  const MIXED_IMPRINT = {
    imprintList: [
      { ids: [7], name: "" },
      { ids: [8], name: "DC Zoom" },
    ],
  };

  test("the field blanks instead of pre-filling the named value", async () => {
    const wrapper = await mountPanel({ md: MIXED_IMPRINT });
    expect(wrapper.vm.patch.imprint).toBe("");
    expect(wrapper.vm.hasChanges).toBe(false);
  });

  test("the dropdown still offers the named value and flags it ambiguous", async () => {
    const wrapper = await mountPanel({ md: MIXED_IMPRINT });
    expect(wrapper.vm.collectionOptions("imprint")).toEqual(["DC Zoom"]);
    expect(wrapper.vm.collectionPlaceholder("imprint")).toBe(MULTI_PLACEHOLDER);
  });

  test("picking the named value enables Save and writes it to all", async () => {
    const wrapper = await mountPanel({ md: MIXED_IMPRINT });
    wrapper.vm.patch.imprint = "DC Zoom";
    await flushPromises();
    expect(wrapper.vm.hasChanges).toBe(true);
    expect(wrapper.vm.buildPatch().imprint).toEqual({ name: "DC Zoom" });
  });

  test("a null name (numeric collection default) counts as the unnamed state", async () => {
    // Volume's default name is null rather than "" — it must blank too.
    const wrapper = await mountPanel({
      md: {
        volumeList: [
          { ids: [1], name: null },
          { ids: [2], name: 5 },
        ],
      },
    });
    expect(wrapper.vm.collectionOptions("volume")).toEqual([5]);
    expect(wrapper.vm.patch.volume).toBe("");
    expect(wrapper.vm.collectionPlaceholder("volume")).toBe(MULTI_PLACEHOLDER);
  });
});

describe("EditPanel — single-value collections (no regression)", () => {
  test("a sole publisher is pre-filled with no multiple placeholder", async () => {
    const wrapper = await mountPanel({
      md: { publisherList: [{ ids: [1], name: "Marvel" }] },
    });
    expect(wrapper.vm.patch.publisher).toBe("Marvel");
    expect(wrapper.vm.collectionOptions("publisher")).toEqual(["Marvel"]);
    expect(wrapper.vm.collectionPlaceholder("publisher")).toBeUndefined();
    expect(wrapper.vm.hasChanges).toBe(false);
  });

  test("a sole volume keeps its numeric value", async () => {
    const wrapper = await mountPanel({
      md: { volumeList: [{ ids: [1], name: 1 }] },
    });
    expect(wrapper.vm.patch.volume).toBe(1);
  });
});

describe("EditPanel — collection inputs render as comboboxes", () => {
  test("publisher / imprint / series / volume are comboboxes", async () => {
    const wrapper = await mountPanel({
      md: { publisherList: [{ ids: [1], name: "Marvel" }] },
    });
    // The four collection fields plus any other comboboxes on the panel.
    expect(wrapper.findAll(".v-combobox").length).toBeGreaterThanOrEqual(4);
  });
});

export default {};
