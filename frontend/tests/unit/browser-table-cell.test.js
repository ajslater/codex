/*
 * Tests for ``browser-table-cell.vue`` — the per-cell renderer
 * that drives table-view rows. Focus areas:
 *
 * - Compound issue cell (split-justified number + suffix).
 * - List / M2M cell (joined comma-list).
 * - Bool cell (Yes / No).
 * - Type-aware text formatting (size, date, datetime).
 * - Enum-code expansion (reading_direction).
 * - Defensive handling of null / stale payloads.
 * - Reading Lists cell (the list menu, for a single-id row, then the names).
 *
 * Mounts the component with a stubbed Pinia store so the
 * ``twentyFourHourTime`` setting is available without a full
 * application bootstrap.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import BrowserTableCell from "@/components/browser/table/browser-table-cell.vue";
import ReadingListMenu from "@/components/reading-list-menu.vue";
import vuetify from "@/plugins/vuetify";

function mountCell({ column, row, user = null }) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user },
      browser: {
        settings: { twentyFourHourTime: false },
      },
      readingLists: { myLists: [], myListsLoaded: true },
    },
  });
  return mount(BrowserTableCell, {
    props: { column, row },
    global: {
      plugins: [pinia, vuetify],
    },
  });
}

describe("BrowserTableCell — issue compound", () => {
  it("renders the number and suffix in split spans", () => {
    const wrapper = mountCell({
      column: "issue",
      row: { issue: { number: "1", suffix: "a" } },
    });
    expect(wrapper.find(".tableIssueNumber").text()).toBe("1");
    expect(wrapper.find(".tableIssueSuffix").text()).toBe("a");
    expect(wrapper.find(".tableIssueCell").attributes("title")).toBe("1a");
  });

  it("renders only the number when suffix is empty", () => {
    const wrapper = mountCell({
      column: "issue",
      row: { issue: { number: "12", suffix: "" } },
    });
    expect(wrapper.find(".tableIssueNumber").text()).toBe("12");
    expect(wrapper.find(".tableIssueSuffix").text()).toBe("");
  });

  it("falls back gracefully when value is a stale plain string", () => {
    /*
     * If a frontend cache pre-dates the dict-shaped payload, the
     * cell must not crash. The number half receives the string;
     * suffix stays empty.
     */
    const wrapper = mountCell({
      column: "issue",
      row: { issue: "5b" },
    });
    expect(wrapper.find(".tableIssueNumber").text()).toBe("5b");
    expect(wrapper.find(".tableIssueSuffix").text()).toBe("");
  });
});

describe("BrowserTableCell — list / M2M", () => {
  it("joins the values with commas", () => {
    const wrapper = mountCell({
      column: "genres",
      row: { genres: ["Action", "Sci-Fi"] },
    });
    expect(wrapper.find(".tableListCell").text()).toBe("Action, Sci-Fi");
  });

  it("renders empty for missing / empty list", () => {
    const wrapper = mountCell({
      column: "tags",
      row: { tags: [] },
    });
    expect(wrapper.find(".tableListCell").text()).toBe("");
  });

  it("joins the composed alternate-series labels", () => {
    /*
     * ``reprints`` has to be listed in ``M2M_COLUMNS`` or the array
     * falls through to the text cell and stringifies badly.
     */
    const wrapper = mountCell({
      column: "reprints",
      row: { reprints: ["Kapitän Wissenschaft (de)", "Capitan Sciencia v1"] },
    });
    expect(wrapper.find(".tableListCell").text()).toBe(
      "Kapitän Wissenschaft (de), Capitan Sciencia v1",
    );
  });
});

describe("BrowserTableCell — bool", () => {
  it("renders Yes / No", () => {
    expect(
      mountCell({ column: "monochrome", row: { monochrome: true } })
        .find(".tableBoolCell")
        .text(),
    ).toBe("Yes");
    expect(
      mountCell({ column: "monochrome", row: { monochrome: false } })
        .find(".tableBoolCell")
        .text(),
    ).toBe("No");
  });

  it("renders empty when value is null", () => {
    const wrapper = mountCell({
      column: "monochrome",
      row: { monochrome: null },
    });
    expect(wrapper.find(".tableBoolCell").text()).toBe("");
  });
});

describe("BrowserTableCell — type-aware text formatters", () => {
  it("formats size in human-readable bytes", () => {
    /*
     * pretty-bytes returns "1.02 kB" or "1 kB" depending on
     * locale. Just assert the cell renders something containing
     * a "B" suffix and the source kilobyte hint.
     */
    const wrapper = mountCell({
      column: "size",
      row: { size: 1024 },
    });
    const text = wrapper.find(".tableTextCell").text();
    expect(text).toMatch(/\bkB\b/v);
  });

  it("formats date as a locale-friendly string", () => {
    const wrapper = mountCell({
      column: "date",
      row: { date: "2024-01-15" },
    });
    const text = wrapper.find(".tableTextCell").text();
    // The locale format varies, but the year should always show.
    expect(text).toMatch(/2024/v);
  });

  it("expands reading_direction enum codes via the choices map", () => {
    const wrapper = mountCell({
      column: "reading_direction",
      row: { readingDirection: "ltr" },
    });
    expect(wrapper.find(".tableTextCell").text()).toBe("Left to Right");
  });

  it("falls back to the raw code for unknown reading_direction values", () => {
    const wrapper = mountCell({
      column: "reading_direction",
      row: { readingDirection: "xyz" },
    });
    expect(wrapper.find(".tableTextCell").text()).toBe("xyz");
  });

  it("renders empty for null / undefined values", () => {
    expect(
      mountCell({ column: "year", row: { year: null } })
        .find(".tableTextCell")
        .text(),
    ).toBe("");
    expect(
      mountCell({ column: "year", row: {} }).find(".tableTextCell").text(),
    ).toBe("");
  });

  it("stringifies plain values straight through", () => {
    const wrapper = mountCell({
      column: "name",
      row: { name: "Corvan the Barbarian" },
    });
    expect(wrapper.find(".tableTextCell").text()).toBe("Corvan the Barbarian");
  });
});

describe("BrowserTableCell — snake_case to camelCase", () => {
  it("reads ``page_count`` from ``pageCount`` on the row", () => {
    /*
     * Backend serializes snake_case via DRF's camelcase middleware.
     * The cell snake-to-camels the column key before lookup so
     * callers don't have to handle the encoding boundary.
     */
    const wrapper = mountCell({
      column: "page_count",
      row: { pageCount: 42 },
    });
    expect(wrapper.find(".tableTextCell").text()).toBe("42");
  });
});

describe("BrowserTableCell — cover", () => {
  const COVER_ROW = { pk: 7, name: "Fight Club 3", coverPk: 42 };

  it("renders the cover through the shared popup component", () => {
    const wrapper = mountCell({ column: "cover", row: COVER_ROW });
    const img = wrapper.find("img");

    expect(img.exists()).toBe(true);
    expect(img.attributes("alt")).toBe("Fight Club 3");
    expect(img.attributes("title")).toBe("Fight Club 3");
    // The look .tableCoverThumb used to carry.
    const style = img.attributes("style");
    expect(style).toContain("border-radius: 2px");
    expect(style).toContain("object-fit: cover");
    expect(style).toContain("height: 100%");
  });

  it("is openable, which the old click-only popup was not", () => {
    const img = mountCell({ column: "cover", row: COVER_ROW }).find("img");

    expect(img.attributes("role")).toBe("button");
    expect(img.attributes("tabindex")).toBe("0");
  });

  it("a broken cover shows the placeholder with nothing to open", async () => {
    const wrapper = mountCell({ column: "cover", row: COVER_ROW });

    await wrapper.find("img").trigger("error");

    // Enlarging a placeholder svg tells the user nothing.
    expect(wrapper.find('[role="button"]').exists()).toBe(false);
    expect(wrapper.find("img").exists()).toBe(true);
  });
});

describe("BrowserTableCell — reading lists", () => {
  const user = { pk: 1 };

  it("renders the list menu for a comic row", () => {
    const wrapper = mountCell({
      column: "reading_lists",
      row: { pk: 42 },
      user,
    });
    const menu = wrapper.findComponent(ReadingListMenu);
    expect(menu.props()).toMatchObject({ collection: "comics", pk: 42 });
    expect(wrapper.find(".tableReadingListsCell button").exists()).toBe(true);
  });

  it("uses the row's collection and single id for a collection row", () => {
    const wrapper = mountCell({
      column: "reading_lists",
      row: { collection: "series", ids: [7], pk: 7 },
      user,
    });
    expect(wrapper.findComponent(ReadingListMenu).props()).toMatchObject({
      collection: "series",
      pk: 7,
    });
  });

  it("renders no menu for a row that aggregates several ids", () => {
    const wrapper = mountCell({
      column: "reading_lists",
      row: { collection: "folders", ids: [1, 2] },
      user,
    });
    expect(wrapper.find(".tableReadingListsCell").exists()).toBe(true);
    expect(wrapper.findComponent(ReadingListMenu).exists()).toBe(false);
  });

  it("renders no button for an anonymous session", () => {
    const wrapper = mountCell({ column: "reading_lists", row: { pk: 42 } });
    expect(wrapper.find(".tableReadingListsCell button").exists()).toBe(false);
  });

  it("names the row's lists after the menu", () => {
    const wrapper = mountCell({
      column: "reading_lists",
      row: { pk: 42, readingLists: ["Favorites", "Want to Read"] },
      user,
    });
    const names = wrapper.find(".tableReadingListsCell .tableListCell");
    expect(names.text()).toBe("Favorites, Want to Read");
    const cell = wrapper.find(".tableReadingListsCell").element;
    expect(cell.firstElementChild.classList).toContain("tableListMenu");
  });
});
