/*
 * Tests for the tag editor's series end year, status and summary.
 *
 * MetronInfo v1.2 holds them in its Series element, so they behave like
 * Start Year:
 *   - They seed from the series and are METRON_INFO-only, with the usual
 *     disabled tooltip under ComicInfo alone.
 *   - They ride the comicbox series object with its name, volume count and
 *     start year, under comicbox's key names; a clear drops the key.
 *   - A save is one tag write; nothing else is posted.
 *   - End Year refuses the years MetronInfo would silently drop: any end
 *     year of an Ongoing series, or one before the start year.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/api/v4/base", () => ({
  HTTP: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

import { HTTP } from "@/api/v4/base";
import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import vuetify from "@/plugins/vuetify";

const DISABLED_TIP = "Not supported by selected metadata formats";
const SERIES_FIELDS = Object.freeze([
  "end_year",
  "series_status",
  "series_summary",
]);
const SERIES_MD = Object.freeze({
  seriesList: Object.freeze([{ name: "S", ids: [1] }]),
  seriesVolumeCount: 3,
  seriesStartYear: 1963,
  seriesEndYear: 1996,
  seriesStatus: "Completed",
  seriesSummary: "A run.",
});

async function mountPanel({ formats = ["METRON_INFO"] } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      metadata: { md: { ...SERIES_MD } },
      admin: { taggingDefaults: { defaultFormats: formats } },
      browser: { settings: { twentyFourHourTime: false } },
    },
  });
  const wrapper = mount(EditPanel, {
    props: { book: { pk: 1, collection: "series", ids: [1] } },
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

const postedUrls = () => vi.mocked(HTTP.post).mock.calls.map(([url]) => url);

beforeEach(() => {
  vi.mocked(HTTP.post).mockReset();
  vi.mocked(HTTP.post).mockResolvedValue({ data: {} });
});

describe("EditPanel — series end year, status and summary", () => {
  test("they seed from the series and render their own inputs", async () => {
    const wrapper = await mountPanel();
    expect(wrapper.vm.patch.end_year).toBe(1996);
    expect(wrapper.vm.patch.series_status).toBe("Completed");
    expect(wrapper.vm.patch.series_summary).toBe("A run.");
    const labels = wrapper.findAll("label").map((el) => el.text());
    expect(labels).toEqual(
      expect.arrayContaining(["End Year", "Status", "Series Summary"]),
    );
  });

  test("they are METRON_INFO-only", async () => {
    const comicInfo = await mountPanel({ formats: ["COMIC_INFO"] });
    const metron = await mountPanel({ formats: ["METRON_INFO"] });
    for (const field of SERIES_FIELDS) {
      expect(comicInfo.vm.isFieldDisabled(field)).toBe(true);
      expect(metron.vm.isFieldDisabled(field)).toBe(false);
    }
  });

  test("disabled, the summary explains why and no hint shows", async () => {
    const wrapper = await mountPanel({ formats: ["COMIC_INFO"] });
    const summary = wrapper
      .findAll("textarea")
      .find((el) => el.element.disabled && el.element.value === "A run.");
    expect(
      summary.element.closest(`[title="${CSS.escape(DISABLED_TIP)}"]`),
    ).toBeTruthy();
    expect(wrapper.text()).not.toContain("saved in Codex only");
  });

  test("they ride the series object under comicbox's keys", async () => {
    const wrapper = await mountPanel();
    await setField(wrapper, "end_year", "1998");
    expect(wrapper.vm.buildPatch().patch.series).toEqual({
      name: "S",
      volume_count: 3,
      start_year: 1963,
      end_year: 1998,
      status: "Completed",
      summary: "A run.",
    });
  });

  test("clearing them drops their keys from the series object", async () => {
    const wrapper = await mountPanel();
    for (const field of SERIES_FIELDS) {
      wrapper.vm.toggleClear(field);
    }
    await flushPromises();
    expect(wrapper.vm.buildPatch().patch.series).toEqual({
      name: "S",
      volume_count: 3,
      start_year: 1963,
    });
  });

  test("a save posts the tag write and nothing else", async () => {
    const wrapper = await mountPanel();
    await setField(wrapper, "series_status", "Cancelled");
    await wrapper.vm.preSave();
    expect(postedUrls()).toEqual([
      "/admin/tag-write/preflight",
      "/admin/tag-write",
    ]);
    const [, payload] = vi.mocked(HTTP.post).mock.calls[1];
    expect(JSON.parse(payload.patch).series.status).toBe("Cancelled");
  });
});

describe("EditPanel — End Year rule", () => {
  test("an Ongoing series has no end year", async () => {
    const wrapper = await mountPanel();
    await setField(wrapper, "series_status", "Ongoing");
    expect(wrapper.vm.endYearConflict(1996)).toBe(
      "An Ongoing series has no end year",
    );
    expect(wrapper.vm.endYearConflict("")).toBe(true);
  });

  test("the end year cannot precede the start year", async () => {
    const wrapper = await mountPanel();
    expect(wrapper.vm.endYearConflict("1950")).toBe(
      "End year precedes start year",
    );
    expect(wrapper.vm.endYearConflict("1963")).toBe(true);
    wrapper.vm.toggleClear("start_year");
    await flushPromises();
    expect(wrapper.vm.endYearConflict("1950")).toBe(true);
  });

  test("a conflict blocks the save", async () => {
    const wrapper = await mountPanel();
    await setField(wrapper, "series_status", "Ongoing");
    await wrapper.vm.preSave();
    expect(HTTP.post).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("An Ongoing series has no end year");
  });

  test("it is off while the format can't write the end year", async () => {
    const wrapper = await mountPanel({ formats: ["COMIC_INFO"] });
    await setField(wrapper, "series_status", "Ongoing");
    await wrapper.vm.preSave();
    expect(postedUrls()).toContain("/admin/tag-write");
  });
});
