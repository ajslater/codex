/*
 * Tests for the tag edit panel's community rating pair.
 *
 * Behavior locked in here:
 *   - buildPatch assembles the nested comicbox shape
 *     {community_rating: {average_rating, rating_count}} whenever either
 *     part changed, clamping the average to 0.0-5.0 at one decimal.
 *   - Clearing (or blanking) the average clears the whole key — a count
 *     alone can't persist (MetronInfo requires AverageRating) — via a
 *     comicbox delete key, since a merge write can't remove values — and
 *     the count rule flags count-only input as invalid.
 *   - Per-format enablement: the average follows COMIC_INFO/METRON_INFO;
 *     the count is METRON_INFO-only.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import vuetify from "@/plugins/vuetify";

async function mountPanel({ formats = ["COMIC_INFO"], md = {} } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      metadata: { md },
      admin: { taggingDefaults: { defaultFormats: formats } },
      browser: { settings: { twentyFourHourTime: false } },
    },
  });
  const wrapper = mount(EditPanel, {
    props: { book: { pk: 1, collection: "comics", ids: [1] } },
    global: { plugins: [pinia, vuetify] },
  });
  await flushPromises();
  return wrapper;
}

describe("EditPanel — community rating pair", () => {
  test("average and count build the nested comicbox shape", async () => {
    const wrapper = await mountPanel();
    wrapper.vm.patch.community_rating = 4.5;
    wrapper.vm.patch.community_rating_count = 100;
    wrapper.vm.onFieldInput("community_rating");
    wrapper.vm.onFieldInput("community_rating_count");
    await flushPromises();
    expect(wrapper.vm.buildPatch().patch.community_rating).toEqual({
      average_rating: 4.5,
      rating_count: 100,
    });
  });

  test("an out-of-range average clamps to 5.0", async () => {
    const wrapper = await mountPanel();
    wrapper.vm.patch.community_rating = 11;
    wrapper.vm.onFieldInput("community_rating");
    await flushPromises();
    expect(wrapper.vm.buildPatch().patch.community_rating).toEqual({
      average_rating: 5,
    });
  });

  test("changing only the count still sends the current average", async () => {
    const wrapper = await mountPanel({
      md: { communityRating: "4.0", communityRatingCount: 10 },
    });
    wrapper.vm.patch.community_rating_count = 25;
    wrapper.vm.onFieldInput("community_rating_count");
    await flushPromises();
    expect(wrapper.vm.buildPatch().patch.community_rating).toEqual({
      average_rating: 4,
      rating_count: 25,
    });
  });

  test("clearing the average clears the whole key", async () => {
    const wrapper = await mountPanel({
      md: { communityRating: "4.0", communityRatingCount: 10 },
    });
    wrapper.vm.toggleClear("community_rating");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("community_rating");
    expect(patch).not.toHaveProperty("community_rating");
  });

  test("a count without an average fails its rule", async () => {
    const wrapper = await mountPanel();
    wrapper.vm.patch.community_rating_count = 50;
    const results = wrapper.vm.communityRatingCountRules.map((rule) =>
      rule(50),
    );
    expect(results).toContain("Requires a community rating");
  });

  test("the count field is METRON_INFO-only", async () => {
    const comicInfoOnly = await mountPanel({ formats: ["COMIC_INFO"] });
    expect(comicInfoOnly.vm.isFieldDisabled("community_rating")).toBe(false);
    expect(comicInfoOnly.vm.isFieldDisabled("community_rating_count")).toBe(
      true,
    );
    const metron = await mountPanel({ formats: ["METRON_INFO"] });
    expect(metron.vm.isFieldDisabled("community_rating")).toBe(false);
    expect(metron.vm.isFieldDisabled("community_rating_count")).toBe(false);
  });
});
