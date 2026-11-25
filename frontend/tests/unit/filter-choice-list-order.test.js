/*
 * The filter's choice list sorts by title, except where the server's order
 * means something: the Reading Lists filter offers your own lists first,
 * then the global ones, each group by name; the Reading List Kind is Mine,
 * Curated, From Tags.
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

function titles(name, choices = CHOICES) {
  const wrapper = mount(BrowserFilterChoiceList, {
    global: { plugins: [createTestingPinia(), vuetify] },
    props: { name, choices, filter: [], search: "" },
  });
  return wrapper.vm.vuetifyItems.map((item) => item.title);
}

describe("filter choice order", () => {
  test("reading lists keep the server's order: your own first", () => {
    expect(titles("readingLists")).toEqual([
      "Want to Read",
      "Zebra",
      "Civil War",
    ]);
  });

  test("reading list kinds keep the server's order", () => {
    expect(titles("readingListKind", KIND_CHOICES)).toEqual([
      "Mine",
      "Curated",
      "From Tags",
    ]);
  });

  test("other filters sort by title", () => {
    expect(titles("characters")).toEqual([
      "Civil War",
      "Want to Read",
      "Zebra",
    ]);
  });
});
