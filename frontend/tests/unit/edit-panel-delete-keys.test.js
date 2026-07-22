/*
 * Tests for buildPatch()'s cleared-field handling.
 *
 * A merge write can only add or replace values — comicbox prunes empty patch
 * values on schema load — so clearing a field in the tag editor must emit the
 * comicbox key into deleteKeys (the write API's explicit clear mechanism)
 * instead of a dead-end empty marker in the patch. Regression: every "clear
 * field" action used to be a silent no-op on the archive.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

vi.mock("@/api/v4/base", () => ({
  HTTP: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

import { HTTP } from "@/api/v4/base";
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

describe("EditPanel — cleared fields become deleteKeys", () => {
  test("clearing a text field deletes instead of patching empty", async () => {
    const wrapper = await mountPanel({ md: { summary: "old words" } });
    wrapper.vm.clearField("summary");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("summary");
    expect(patch).not.toHaveProperty("summary");
  });

  test("manually emptying a text field also deletes", async () => {
    const wrapper = await mountPanel({ md: { summary: "old words" } });
    wrapper.vm.patch.summary = "";
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("summary");
    expect(patch).not.toHaveProperty("summary");
  });

  test("clearing a tag array deletes its comicbox key", async () => {
    const wrapper = await mountPanel({
      md: { characters: [{ pk: 1, name: "Spider-Man" }] },
    });
    wrapper.vm.clearField("characters");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("characters");
    expect(patch).not.toHaveProperty("characters");
  });

  test("clearing story arcs deletes the comicbox 'arcs' key", async () => {
    const wrapper = await mountPanel({
      md: { storyArcNumbers: [{ name: "Arc", number: 1 }] },
    });
    wrapper.vm.clearField("story_arcs");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("arcs");
    expect(patch).not.toHaveProperty("arcs");
  });

  test("clearing the community rating deletes instead of patching null", async () => {
    const wrapper = await mountPanel({ md: { communityRating: 4.5 } });
    wrapper.vm.clearField("community_rating");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("community_rating");
    expect(patch).not.toHaveProperty("community_rating");
  });

  test("clearing the publisher deletes the whole group key", async () => {
    const wrapper = await mountPanel({
      md: { publisherList: [{ ids: [1], name: "Marvel" }] },
    });
    wrapper.vm.clearField("publisher");
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toContain("publisher");
    expect(patch).not.toHaveProperty("publisher");
  });

  test("a real value still travels in the patch, not deleteKeys", async () => {
    const wrapper = await mountPanel({ md: { summary: "old words" } });
    wrapper.vm.patch.summary = "new words";
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(patch.summary).toBe("new words");
    expect(deleteKeys).not.toContain("summary");
  });

  test("clearing one field leaves edits to another intact", async () => {
    const wrapper = await mountPanel({
      md: { summary: "old words", notes: "keep me" },
    });
    wrapper.vm.clearField("summary");
    wrapper.vm.patch.notes = "edited";
    await flushPromises();
    const { patch, deleteKeys } = wrapper.vm.buildPatch();
    expect(deleteKeys).toEqual(["summary"]);
    expect(patch).toEqual({ notes: "edited" });
  });

  test("a clear-only save posts deleteKeys with an empty patch", async () => {
    // The whole point of the delete_keys mechanism: a save with nothing
    // but clears must still reach the server and write.
    const wrapper = await mountPanel({ md: { summary: "old words" } });
    vi.mocked(HTTP.post).mockResolvedValue({ data: {} });
    wrapper.vm.clearField("summary");
    await flushPromises();
    await wrapper.vm.doSave();

    expect(HTTP.post).toHaveBeenCalledWith(
      "/admin/tag-write",
      expect.objectContaining({ deleteKeys: ["summary"], patch: "{}" }),
    );
  });
});
