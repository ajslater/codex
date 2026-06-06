/*
 * Regression test for the tag-edit screen's Identifiers section.
 *
 * Bug: the metadata endpoint shapes identifiers as
 *   {pk, source, type, code, displayName, url}
 * but initFromMetadata() still parsed the legacy {name, key} fields. A comic
 * with four identifiers rendered four rows (length matched) yet every Source /
 * Type / Key field was blank because the parsed fields did not exist.
 *
 * This mounts the real EditPanel, seeds the metadata store with shaped
 * identifiers, and asserts the edit form's local `identifiers` are populated
 * with source / id_type / key — the values the v-select / v-text-field bind to.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import vuetify from "@/plugins/vuetify";

const SHAPED_IDENTIFIERS = Object.freeze([
  {
    pk: 1,
    source: "comicvine",
    type: "comic",
    code: "111",
    displayName: "Comic Vine",
    url: "",
  },
  {
    pk: 2,
    source: "metron",
    type: "series",
    code: "222",
    displayName: "Metron Cloud",
    url: "",
  },
  {
    pk: 3,
    source: "grandcomicsdatabase",
    type: "publisher",
    code: "333",
    displayName: "Grand Comics Database",
    url: "",
  },
  {
    pk: 4,
    source: "marvel",
    type: "character",
    code: "444",
    displayName: "Marvel",
    url: "",
  },
]);

function mountPanel(identifiers = SHAPED_IDENTIFIERS) {
  const pinia = createTestingPinia({
    initialState: {
      metadata: { md: { collection: "comics", identifiers } },
    },
  });
  const wrapper = mount(EditPanel, {
    global: { plugins: [pinia, vuetify] },
    props: { book: { collection: "comics", pk: 1 } },
  });
  return { wrapper };
}

describe("EditPanel identifiers", () => {
  test("populates every field from the shaped payload", () => {
    const { wrapper } = mountPanel();

    expect(wrapper.vm.identifiers).toStrictEqual([
      { source: "comicvine", id_type: "comic", key: "111" },
      { source: "metron", id_type: "series", key: "222" },
      { source: "grandcomicsdatabase", id_type: "publisher", key: "333" },
      { source: "marvel", id_type: "character", key: "444" },
    ]);
  });

  test("renders one populated row per identifier, none blank", () => {
    const { wrapper } = mountPanel();

    // length matches AND no field is empty (the symptom was N blank rows).
    expect(wrapper.vm.identifiers).toHaveLength(SHAPED_IDENTIFIERS.length);
    for (const row of wrapper.vm.identifiers) {
      expect(row.source).toBeTruthy();
      expect(row.id_type).toBeTruthy();
      expect(row.key).toBeTruthy();
    }
  });

  test("leaves identifiers empty when the comic has none", () => {
    const { wrapper } = mountPanel([]);
    expect(wrapper.vm.identifiers).toStrictEqual([]);
  });
});

export default {};
