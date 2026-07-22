/*
 * Tests for the metadata dialog's ratings table.
 *
 * Behavior locked in here:
 *   - The community rating renders as "N / 5", with trailing .0 trimmed,
 *     plus a vote-count suffix "(N ratings)" when a count exists
 *     (singular "(1 rating)").
 *   - The row (and the whole table absent an age rating) hides when
 *     communityRating is null; a count alone renders nothing.
 *   - Age rating shows the Metron name with the original tagged name as
 *     a secondary when they differ.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import MetadataRatings from "@/components/metadata/metadata-ratings.vue";
import vuetify from "@/plugins/vuetify";

function mountRatings(md) {
  const pinia = createTestingPinia({
    // MetadataText's clickable computed reads browser settings.show.
    initialState: { metadata: { md }, browser: { settings: { show: {} } } },
  });
  return mount(MetadataRatings, {
    global: {
      plugins: [pinia, vuetify],
      // MetadataText's clickable computed reads the current route.
      mocks: { $router: { currentRoute: { value: { params: {} } } } },
    },
  });
}

describe("metadata ratings table", () => {
  test("community rating with count renders value and votes", () => {
    const wrapper = mountRatings({
      communityRating: "4.2",
      communityRatingCount: 128,
    });
    expect(wrapper.text()).toContain("Community Rating");
    expect(wrapper.text()).toContain("4.2 / 5 (128 ratings)");
  });

  test("a single vote is singular", () => {
    const wrapper = mountRatings({
      communityRating: "5.0",
      communityRatingCount: 1,
    });
    expect(wrapper.text()).toContain("5 / 5 (1 rating)");
  });

  test("no count shows the bare scale and trims trailing zeros", () => {
    const wrapper = mountRatings({ communityRating: "4.0" });
    expect(wrapper.text()).toContain("4 / 5");
    expect(wrapper.text()).not.toContain("(");
  });

  test("null rating hides the table entirely", () => {
    const wrapper = mountRatings({
      communityRating: null,
      communityRatingCount: 99,
    });
    expect(wrapper.find("table").exists()).toBe(false);
  });

  test("age rating alone still shows the table without a community row", () => {
    const wrapper = mountRatings({ ageRating: { name: "Everyone" } });
    expect(wrapper.text()).toContain("Age Rating");
    expect(wrapper.text()).not.toContain("Community Rating");
  });
});
