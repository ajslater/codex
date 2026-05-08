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
 *
 * Mounts the component with a stubbed Pinia store so the
 * ``twentyFourHourTime`` setting is available without a full
 * application bootstrap.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import BrowserTableCell from "@/components/browser/table/browser-table-cell.vue";
import vuetify from "@/plugins/vuetify";

function mountCell({ column, row, twentyFourHourTime = false }) {
  const pinia = createTestingPinia({
    initialState: {
      browser: {
        settings: { twentyFourHourTime },
      },
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
    expect(text).toMatch(/\bkB\b/);
  });

  it("formats date as a locale-friendly string", () => {
    const wrapper = mountCell({
      column: "date",
      row: { date: "2024-01-15" },
    });
    const text = wrapper.find(".tableTextCell").text();
    // The locale format varies, but the year should always show.
    expect(text).toMatch(/2024/);
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
      row: { name: "Conan the Barbarian" },
    });
    expect(wrapper.find(".tableTextCell").text()).toBe("Conan the Barbarian");
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
