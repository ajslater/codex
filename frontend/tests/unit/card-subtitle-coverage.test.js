/*
 * A reading list's card leads with its name, then its sources, then "31 of
 * 98" when the library lacks some of it.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

import BrowserCardSubtitle from "@/components/browser/card/subtitle.vue";
import vuetify from "@/plugins/vuetify";

function subtitle(item) {
  return mount(BrowserCardSubtitle, {
    props: { item: { collection: "arcs", name: "Civil War", ...item } },
    global: {
      plugins: [
        createTestingPinia({ createSpy: vi.fn, stubActions: false }),
        vuetify,
      ],
    },
  });
}

describe("list coverage on a card", () => {
  test("a list with gaps says how much is here", () => {
    const wrapper = subtitle({ listInLibrary: 31, listTotal: 98 });
    expect(wrapper.find(".listCoverage").text()).toBe("31 of 98");
  });

  test("a complete list says nothing", () => {
    const wrapper = subtitle({ listInLibrary: 4, listTotal: 4 });
    expect(wrapper.find(".listCoverage").exists()).toBe(false);
  });

  test("another card says nothing", () => {
    const wrapper = subtitle({ collection: "series" });
    expect(wrapper.find(".listCoverage").exists()).toBe(false);
  });
});

function lines(wrapper) {
  return [...wrapper.element.children].map((el) => [
    el.className,
    el.textContent.trim(),
  ]);
}

describe("a reading list's card caption", () => {
  test("its name comes first, bold, and its sources after", () => {
    const wrapper = subtitle({
      listSources: "Tags, Metron · CBRO",
      listInLibrary: 31,
      listTotal: 98,
    });
    const [first, ...rest] = lines(wrapper);
    expect(first[1]).toBe("Civil War");
    expect(first[0]).toContain("listName");
    expect(rest.map(([, text]) => text)).toEqual([
      "Tags, Metron · CBRO",
      "31 of 98",
    ]);
  });

  test("another card keeps its name last", () => {
    const wrapper = subtitle({
      collection: "imprints",
      publisherName: "Marlow",
    });
    const names = lines(wrapper).map(([, text]) => text);
    expect(names.at(-1)).toBe("Civil War");
    expect(wrapper.find(".listName").exists()).toBe(false);
  });
});
