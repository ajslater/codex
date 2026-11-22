/*
 * The filter's choice list sorts by title, except where the server's order
 * means something: the Reading Lists filter offers your own lists first,
 * then the global ones, each group by name.
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

function titles(name) {
  const wrapper = mount(BrowserFilterChoiceList, {
    global: { plugins: [createTestingPinia(), vuetify] },
    props: { name, choices: CHOICES, filter: [], search: "" },
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

  test("other filters sort by title", () => {
    expect(titles("characters")).toEqual([
      "Civil War",
      "Want to Read",
      "Zebra",
    ]);
  });
});
