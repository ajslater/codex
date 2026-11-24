/*
 * A reading list's details in the metadata dialog, and Continue Reading.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

vi.mock("@/api/v4/reading-lists", () => ({
  getContinue: vi.fn(),
  exportURL: (pk, fmt, isMissing) =>
    `/export/${pk}/${fmt}${isMissing ? "?missing=1" : ""}`,
}));
vi.mock("@/plugins/router", () => ({
  default: {
    push: vi.fn(),
    currentRoute: { value: { params: {}, query: {} } },
  },
}));

import * as API from "@/api/v4/reading-lists";
import MetadataReadingListDetails from "@/components/metadata/metadata-reading-list-details.vue";
import router from "@/plugins/router";
import vuetify from "@/plugins/vuetify";
import { useCommonStore } from "@/stores/common";
import { useMetadataStore } from "@/stores/metadata";
import { useReadingListsStore } from "@/stores/reading-lists";

const DETAILS = Object.freeze({
  pk: 5,
  name: "Civil War",
  description: "Heroes take sides.",
  listType: "event",
  startYear: 2006,
  endYear: 2007,
  sources: [
    {
      kind: "catalog",
      label: "DieselTech Catalog",
      attribution: "cbro",
      attributionUrl: "https://cbro.invalid/cw",
    },
  ],
  total: 98,
  inLibrary: 31,
  missing: 67,
  read: 12,
  previous: { pk: 4, name: "House of M" },
  next: { pk: null, name: "Secret Invasion" },
  continue: { pk: 9, page: 3 },
  editable: false,
  personal: false,
});

function mountDetails(details) {
  const pinia = createTestingPinia({ createSpy: vi.fn, stubActions: false });
  useMetadataStore().md = { readingListDetails: details };
  const wrapper = mount(MetadataReadingListDetails, {
    global: { plugins: [pinia, vuetify], mocks: { $router: router } },
  });
  return wrapper;
}

describe("MetadataReadingListDetails", () => {
  test("says what the list is and how much is here", () => {
    const text = mountDetails(DETAILS).text();
    expect(text).toContain("Event");
    expect(text).toContain("2006–2007");
    expect(text).toContain("31 of 98 in the library, 12 read");
    expect(text).toContain("Heroes take sides.");
    expect(text).toContain("CBRO");
  });

  test("links the list before it, names the one not here", () => {
    const wrapper = mountDetails(DETAILS);
    const links = wrapper.findAll("a").map((a) => a.text());
    expect(links).toContain("House of M");
    expect(wrapper.text()).toContain("Secret Invasion (not in the library)");
  });

  test("Continue Reading is off, with why, when everything is read", () => {
    const wrapper = mountDetails({ ...DETAILS, continue: null });
    const button = wrapper
      .findAll("button")
      .find((b) => b.text() === "Continue Reading");
    expect(button.attributes("disabled")).toBeDefined();
    // In words beside it: a title never shows on a disabled button.
    expect(wrapper.find(".detailsActions").text()).toContain("Every issue");
  });

  test("nothing for a selection that is not one list", () => {
    expect(mountDetails(null).find(".readingListDetails").exists()).toBe(false);
  });
});

describe("continueReading", () => {
  test("opens the first unfinished issue with the list as its order", async () => {
    createTestingPinia({ createSpy: vi.fn, stubActions: false });
    API.getContinue.mockResolvedValue({
      data: { continue: { pk: 9, page: 3 } },
    });
    await useReadingListsStore().continueReading(5);
    await flushPromises();
    expect(router.push).toHaveBeenCalledWith({
      name: "reader",
      params: { pk: 9 },
      query: { page: 3, list: 5 },
    });
  });

  test("says so when the list is read", async () => {
    createTestingPinia({ createSpy: vi.fn, stubActions: false });
    API.getContinue.mockResolvedValue({ data: { continue: null } });
    await useReadingListsStore().continueReading(5);
    expect(useCommonStore().setNotice).toHaveBeenCalledWith(
      "You have read every issue of this list.",
    );
  });
});
