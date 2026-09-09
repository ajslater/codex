/*
 * The tag editor's comicbox 5 fields.
 *
 * ComicInfo compounds "is manga" and "reads right to left" into one
 * YesAndRightToLeft value; comicbox 5 reports each separately, so the
 * editor has a field for each. MetronInfo carries a MangaVolume string
 * and ComicInfo does not, so the two formats support different halves.
 * Web links are the ones the file itself carries: the links beside an
 * identifier are built from its key and are never written back.
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

describe("EditPanel manga fields", () => {
  test("seeds both facts from the metadata", async () => {
    const wrapper = await mountPanel({
      md: { manga: "Yes", mangaVolume: "1-3" },
    });

    expect(wrapper.vm.patch.manga).toBe("Yes");
    expect(wrapper.vm.patch.manga_volume).toBe("1-3");
  });

  test("offers exactly comicbox's three manga values", async () => {
    const wrapper = await mountPanel({ formats: ["COMIC_INFO"] });

    expect(wrapper.vm.mangaItems).toStrictEqual(["Yes", "No", "Unknown"]);
  });

  test("each format supports the half it can store", async () => {
    const comicInfo = await mountPanel({ formats: ["COMIC_INFO"] });
    expect(comicInfo.vm.isFieldDisabled("manga")).toBe(false);
    expect(comicInfo.vm.isFieldDisabled("manga_volume")).toBe(true);

    const metronInfo = await mountPanel({ formats: ["METRON_INFO"] });
    expect(metronInfo.vm.isFieldDisabled("manga_volume")).toBe(false);
  });

  test("writes each as its own key", async () => {
    const wrapper = await mountPanel({ md: { manga: "No" } });
    wrapper.vm.patch.manga = "Yes";
    wrapper.vm.patch.manga_volume = "2";
    wrapper.vm.changedFields.add("manga");
    wrapper.vm.changedFields.add("manga_volume");

    const { patch } = wrapper.vm.buildPatch();
    expect(patch.manga).toBe("Yes");
    expect(patch.manga_volume).toBe("2");
  });
});

describe("EditPanel web links", () => {
  const URLS = Object.freeze([
    "https://example.com/one",
    "https://example.com/two",
  ]);

  test("seeds the list the file carries", async () => {
    const wrapper = await mountPanel({ md: { urls: URLS } });
    expect(wrapper.vm.urls).toStrictEqual([...URLS]);
  });

  test("writes the list back, trimmed of blanks", async () => {
    const wrapper = await mountPanel({ md: { urls: URLS } });
    wrapper.vm.urls = [...URLS, "  ", ""];
    wrapper.vm.changedFields.add("urls");

    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(patch.urls).toStrictEqual([...URLS]);
    expect(deleteKeys).not.toContain("urls");
  });

  test("emptying the list clears the key rather than writing nothing", async () => {
    const wrapper = await mountPanel({ md: { urls: URLS } });
    wrapper.vm.clearField("urls");

    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(wrapper.vm.urls).toStrictEqual([]);
    expect(deleteKeys).toContain("urls");
    expect(patch).not.toHaveProperty("urls");
  });
});

export default {};
