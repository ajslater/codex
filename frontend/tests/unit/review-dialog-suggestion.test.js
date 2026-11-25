/*
 * A missing issue the matcher refused a comic for shows that comic (1053).
 *
 * The row stays missing, says which comic it may be and offers to use it.
 * Accept All Best Guesses takes matched guesses only, so a list whose only
 * review rows are suggestions leaves it off and says why.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

vi.mock("@/api/v4/reading-lists", () => ({
  getEntries: vi.fn(),
  updateEntry: vi.fn(() => Promise.resolve({ data: {} })),
  acceptEntries: vi.fn(),
  getMappings: vi.fn(() => Promise.resolve({ data: { mappings: [] } })),
}));

import * as API from "@/api/v4/reading-lists";
import ReviewDialog from "@/components/admin/tabs/reading-lists/review-dialog.vue";
import vuetify from "@/plugins/vuetify";

const STUBS = Object.freeze({ VDialog: { template: "<div><slot /></div>" } });
const SUGGESTED = Object.freeze({
  pk: 9,
  seriesName: "Burrowman",
  volumeName: "(2011)",
  issue: "1",
  year: 2011,
});

async function mountReview(entries) {
  API.getEntries.mockReset();
  API.getEntries.mockResolvedValue({ data: { entries } });
  const wrapper = mount(ReviewDialog, {
    props: { modelValue: true, readingList: { pk: 3, name: "B", sources: [] } },
    global: {
      plugins: [createTestingPinia({ createSpy: vi.fn }), vuetify],
      stubs: STUBS,
    },
  });
  await flushPromises();
  return wrapper;
}

function suggestedEntry() {
  return {
    pk: 100,
    position: 0,
    seriesName: "Burrowman",
    issue: "1",
    year: 2011,
    ignored: false,
    liveSource: null,
    needsReview: true,
    comic: null,
    suggestedComic: { ...SUGGESTED },
  };
}

describe("A suggested comic in Edit Issues", () => {
  test("the missing row names the suggestion", async () => {
    const wrapper = await mountReview([suggestedEntry()]);
    const text = wrapper.find(".suggestion").text();
    expect(text).toContain("Missing");
    expect(text).toContain("maybe Burrowman (2011) #1");
  });

  test("Use picks the suggested comic", async () => {
    const wrapper = await mountReview([suggestedEntry()]);
    await wrapper.find(".useSuggestion").trigger("click");
    await flushPromises();
    expect(API.updateEntry).toHaveBeenCalledWith(3, 100, { comic: 9 });
  });

  test("Accept All is off when only suggestions need review", async () => {
    const wrapper = await mountReview([suggestedEntry()]);
    const accept = wrapper
      .findAll("button")
      .find((button) => button.text().includes("Accept All Best Guesses"));
    expect(accept.attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("Only missing issues need review");
  });
});
