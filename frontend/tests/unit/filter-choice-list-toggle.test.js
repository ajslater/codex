/*
 * A filter's choice list is a checklist: each row toggles its value in or
 * out of the filter, as the released Shelves sub-menu did. The new filter
 * is worked out from the click and the whole filter, never from what the
 * list shows, so a ticked value the search box hides is kept. Ticked rows
 * come first when the list opens and stay put as you tick.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import BrowserFilterChoiceList from "@/components/browser/toolbars/top/filter-choice-list.vue";
import vuetify from "@/plugins/vuetify";

const CHOICES = Object.freeze([
  { pk: 4, name: "Want to Read" },
  { pk: 7, name: "Zebra" },
  { pk: 1, name: "Civil War" },
]);
const KIND_CHOICES = Object.freeze([
  { pk: "mine", name: "Mine" },
  { pk: "curated", name: "Curated" },
  { pk: "tags", name: "From Tags" },
]);
const METRON_CHOICES = Object.freeze([
  { pk: 1, name: "Everyone", index: 0 },
  { pk: 3, name: "Teen", index: 2 },
  { pk: 6, name: "Adult", index: 5 },
]);
const TAGGED_CHOICES = Object.freeze([
  { pk: 9, name: "T", index: 2, metronName: "Teen" },
]);

function mountList({
  name = "characters",
  choices = CHOICES,
  filter = [],
  search = "",
  matchAll = false,
} = {}) {
  return mount(BrowserFilterChoiceList, {
    global: { plugins: [createTestingPinia(), vuetify] },
    props: { name, choices, filter, search, matchAll },
  });
}

const rows = (wrapper) => wrapper.findAll("[role=menuitemcheckbox]");
const titles = (wrapper) => rows(wrapper).map((row) => row.text());
const row = (wrapper, title) =>
  rows(wrapper).find((candidate) => candidate.text().includes(title));
const lastEmit = (wrapper) => wrapper.emitted("selected").at(-1)[0];

describe("filter choice rows toggle", () => {
  test("ticking a row adds its value to the filter", async () => {
    const wrapper = mountList({ filter: [4] });
    await row(wrapper, "Zebra").trigger("click");
    expect(lastEmit(wrapper)).toEqual([4, 7]);
  });

  test("ticking a ticked row removes its value", async () => {
    const wrapper = mountList({ filter: [4, 7] });
    await row(wrapper, "Want to Read").trigger("click");
    expect(lastEmit(wrapper)).toEqual([7]);
  });

  test("each row says whether it is ticked", () => {
    const wrapper = mountList({ filter: [7] });
    expect(row(wrapper, "Zebra").attributes("aria-checked")).toBe("true");
    expect(row(wrapper, "Civil War").attributes("aria-checked")).toBe("false");
    expect(row(wrapper, "Zebra").find(".v-selection-control").exists()).toBe(
      true,
    );
  });

  test("a ticked value hidden by the search is kept", async () => {
    const wrapper = mountList({ filter: [4, 1], search: "zeb" });
    expect(titles(wrapper)).toEqual(["Zebra"]);
    await row(wrapper, "Zebra").trigger("click");
    expect(lastEmit(wrapper)).toEqual([4, 1, 7]);
  });

  test("a ticked row is drawn at full strength, focused or not", () => {
    /*
     * Plain rows sit at 0.62 opacity unless hovered or focused, so a
     * ticked row read fainter than the one last clicked.
     */
    const wrapper = mountList({ filter: [7, 4] });
    expect(row(wrapper, "Zebra").classes()).toContain("filterChoiceTicked");
    expect(row(wrapper, "Want to Read").classes()).toContain(
      "filterChoiceTicked",
    );
    expect(row(wrapper, "Civil War").classes()).not.toContain(
      "filterChoiceTicked",
    );
  });

  test("a ticked row is never disabled", () => {
    const wrapper = mountList({ filter: [7] });
    expect(row(wrapper, "Zebra").classes()).not.toContain(
      "v-list-item--disabled",
    );
  });
});

describe("ticked rows first", () => {
  test("ticked rows come first when the list opens", () => {
    const wrapper = mountList({ filter: [7] });
    expect(titles(wrapper)).toEqual(["Zebra", "Civil War", "Want to Read"]);
  });

  test("rows stay put as you tick", async () => {
    const wrapper = mountList({ filter: [7] });
    await wrapper.setProps({ filter: [7, 4] });
    expect(titles(wrapper)).toEqual(["Zebra", "Civil War", "Want to Read"]);
    await wrapper.setProps({ filter: [] });
    expect(titles(wrapper)).toEqual(["Zebra", "Civil War", "Want to Read"]);
  });

  test("reading lists: ticked first, then the server's order", () => {
    const wrapper = mountList({ name: "readingLists", filter: [1] });
    expect(titles(wrapper)).toEqual(["Civil War", "Want to Read", "Zebra"]);
  });

  test("the reading list kinds keep their order", () => {
    const wrapper = mountList({
      name: "readingListKind",
      choices: KIND_CHOICES,
      filter: ["tags"],
    });
    expect(titles(wrapper)).toEqual(["Mine", "Curated", "From Tags"]);
  });

  test("age ratings keep rating order", () => {
    const wrapper = mountList({
      name: "ageRatingMetron",
      choices: METRON_CHOICES,
      filter: [6],
    });
    expect(titles(wrapper)).toEqual(["Everyone", "Teen", "Adult"]);
  });
});

describe("the As-tagged tab", () => {
  test("keeps the standardized name after the checkbox", () => {
    const wrapper = mountList({
      name: "ageRatingTagged",
      choices: TAGGED_CHOICES,
      filter: [9],
    });
    const prepend = row(wrapper, "T").find(".v-list-item__prepend");
    const parts = [...prepend.element.children].map((el) => el.className);
    expect(parts[0]).toContain("v-selection-control");
    expect(prepend.find(".metronName").text()).toBe("Teen");
  });
});

const isDimmed = (candidate) =>
  candidate.classes().includes("v-list-item--disabled");

describe("under All", () => {
  const ABC = Object.freeze([
    { pk: 1, name: "Alpha" },
    { pk: 2, name: "Bravo" },
    { pk: 3, name: "Charlie" },
  ]);

  test("a row no longer offered stays in place, dimmed and not tickable", async () => {
    const wrapper = mountList({ choices: ABC, filter: [], matchAll: true });
    await wrapper.setProps({ choices: [ABC[0]], filter: [1] });
    expect(titles(wrapper)).toEqual(["Alpha", "Bravo", "Charlie"]);
    expect(isDimmed(row(wrapper, "Alpha"))).toBe(false);
    expect(isDimmed(row(wrapper, "Bravo"))).toBe(true);
    await row(wrapper, "Bravo").trigger("click");
    expect(wrapper.emitted("selected")).toBeUndefined();
  });

  test("a ticked row is never dimmed", async () => {
    const wrapper = mountList({ choices: ABC, filter: [2], matchAll: true });
    await wrapper.setProps({ choices: [ABC[0]] });
    expect(isDimmed(row(wrapper, "Bravo"))).toBe(false);
    expect(row(wrapper, "Bravo").attributes("aria-checked")).toBe("true");
  });

  test("a row offered again is tickable again", async () => {
    const wrapper = mountList({ choices: ABC, filter: [], matchAll: true });
    await wrapper.setProps({ choices: [ABC[0]] });
    await wrapper.setProps({ choices: ABC });
    expect(isDimmed(row(wrapper, "Bravo"))).toBe(false);
  });

  test("a newly offered row goes after the rows shown", async () => {
    const wrapper = mountList({
      choices: [ABC[1]],
      filter: [],
      matchAll: true,
    });
    await wrapper.setProps({ choices: ABC });
    expect(titles(wrapper)).toEqual(["Bravo", "Alpha", "Charlie"]);
  });

  test("None cannot be ticked, and says why in its row", () => {
    const wrapper = mountList({
      choices: [{ pk: -1, name: "_none_" }, ...ABC],
      filter: [],
      matchAll: true,
    });
    const none = row(wrapper, "None");
    expect(isDimmed(none)).toBe(true);
    expect(none.find(".filterChoiceReason").exists()).toBe(true);
  });

  test("under Any the list is replaced as before", async () => {
    const wrapper = mountList({ choices: ABC, filter: [] });
    await wrapper.setProps({ choices: [ABC[0]] });
    expect(titles(wrapper)).toEqual(["Alpha"]);
  });
});
