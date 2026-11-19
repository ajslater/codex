/*
 * The Reading Lists grid's kind toggle: Mine only for a signed-in user.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

import ReadingListKindToggle from "@/components/browser/toolbars/top/reading-list-kind-toggle.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

function toggle({ user }) {
  const pinia = createTestingPinia({
    createSpy: vi.fn,
    initialState: { auth: { user } },
  });
  return mount(ReadingListKindToggle, {
    global: {
      plugins: [pinia, vuetify],
      mocks: { $route: { params: { collection: "arcs" } } },
    },
  });
}

describe("ReadingListKindToggle", () => {
  test("a signed-in user gets All, Mine, Curated and From Tags", () => {
    const labels = toggle({ user: { pk: 1 } })
      .findAll("button")
      .map((button) => button.text());
    expect(labels).toEqual(["All", "Mine", "Curated", "From Tags"]);
  });

  test("an anonymous session gets no Mine", () => {
    const labels = toggle({ user: null })
      .findAll("button")
      .map((button) => button.text());
    expect(labels).toEqual(["All", "Curated", "From Tags"]);
  });

  test("choosing Mine filters the grid", async () => {
    const wrapper = toggle({ user: { pk: 1 } });
    await wrapper.findAll("button")[1].trigger("click");
    expect(useBrowserStore().setSettings).toHaveBeenCalledWith({
      filters: { readingListKind: "mine" },
    });
  });
});
