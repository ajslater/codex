/*
 * Tests for the tag editor's database-only series attributes.
 *
 * No format codex writes can hold a series' end year, status or summary,
 * so the editor saves them straight to the database:
 *   - They seed from the series, under any write format.
 *   - They lock, with a visible reason, unless exactly one series is being
 *     edited and its name is unchanged.
 *   - A visible hint warns they are not written to the comic files.
 *   - Only changed ones are sent, to /admin/series-attrs, and never ride
 *     the comicbox patch; a save with nothing else skips the tag write.
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
import { useBrowserStore } from "@/stores/browser";

const ONE_SERIES = Object.freeze([{ name: "S", ids: [1] }]);
const SERIES_MD = Object.freeze({
  seriesList: ONE_SERIES,
  seriesStartYear: 1963,
  seriesEndYear: 1996,
  seriesStatus: "Completed",
  seriesSummary: "A run.",
});
const WARNING =
  "End year, status and series summary are saved in Codex only, " +
  "not written to the comic files.";

async function mountPanel({
  formats = ["COMIC_INFO"],
  md = SERIES_MD,
  routeName = "reader",
} = {}) {
  const pinia = createTestingPinia({
    initialState: {
      metadata: { md: { ...md } },
      admin: { taggingDefaults: { defaultFormats: formats } },
      browser: { settings: { twentyFourHourTime: false } },
    },
  });
  const wrapper = mount(EditPanel, {
    props: { book: { pk: 1, collection: "series", ids: [1] } },
    global: {
      plugins: [pinia, vuetify],
      mocks: { $route: { name: routeName } },
    },
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

describe("EditPanel — series attributes seed and render", () => {
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

  test("no write format gates them", async () => {
    const wrapper = await mountPanel({ formats: ["COMIC_INFO"] });
    for (const field of ["end_year", "series_status", "series_summary"]) {
      expect(wrapper.vm.isFieldDisabled(field)).toBe(false);
    }
  });

  test("the hint warns they stay out of the comic files", async () => {
    const wrapper = await mountPanel();
    expect(wrapper.vm.seriesAttrsHint).toBe(WARNING);
    expect(wrapper.text()).toContain(WARNING);
  });
});

describe("EditPanel — series attributes lock", () => {
  test("two series lock them and say why", async () => {
    const wrapper = await mountPanel({
      md: {
        seriesList: [
          { name: "S", ids: [1] },
          { name: "T", ids: [2] },
        ],
      },
    });
    expect(wrapper.vm.isFieldDisabled("end_year")).toBe(true);
    expect(wrapper.vm.seriesAttrsHint).toBe(
      `Edit one series at a time. ${WARNING}`,
    );
  });

  test("renaming the series locks them until it is saved", async () => {
    const wrapper = await mountPanel();
    await setField(wrapper, "series", "Renamed");
    expect(wrapper.vm.isFieldDisabled("series_status")).toBe(true);
    expect(wrapper.vm.seriesAttrsLockReason).toBe(
      "Save the series change first.",
    );
  });
});

describe("EditPanel — series attributes save", () => {
  test("only changed attributes are sent, never in the patch", async () => {
    const wrapper = await mountPanel();
    await setField(wrapper, "end_year", "1998");
    expect(wrapper.vm.buildSeriesAttrs()).toEqual({ endYear: 1998 });
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(patch).toEqual({});
    expect(deleteKeys).toEqual([]);
  });

  test("clears send empty values", async () => {
    const wrapper = await mountPanel();
    for (const field of ["end_year", "series_status", "series_summary"]) {
      wrapper.vm.toggleClear(field);
    }
    await flushPromises();
    expect(wrapper.vm.buildSeriesAttrs()).toEqual({
      endYear: null,
      status: "",
      summary: "",
    });
  });

  test("a database-only save skips the preflight and the tag write", async () => {
    const wrapper = await mountPanel();
    await setField(wrapper, "series_status", "Ongoing");
    await wrapper.vm.preSave();
    expect(postedUrls()).toEqual(["/admin/series-attrs"]);
    expect(HTTP.post).toHaveBeenCalledWith("/admin/series-attrs", {
      collection: "series",
      pks: ["1"],
      status: "Ongoing",
    });
  });

  test("a save with tag edits too posts both", async () => {
    const wrapper = await mountPanel({ md: { ...SERIES_MD, summary: "x" } });
    await setField(wrapper, "series_summary", "A longer run.");
    await setField(wrapper, "summary", "y");
    await wrapper.vm.doSave();
    expect(postedUrls()).toEqual(["/admin/series-attrs", "/admin/tag-write"]);
  });

  test("the browser page reloads so the title years refresh", async () => {
    const wrapper = await mountPanel({ routeName: "browser" });
    await setField(wrapper, "end_year", "1998");
    await wrapper.vm.doSave();
    expect(useBrowserStore().loadBrowserPage).toHaveBeenCalledTimes(1);
  });
});
