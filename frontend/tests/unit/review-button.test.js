/*
 * Tests for the toolbar Review button that announces online-tagging matches.
 *
 * The Match Review dialog no longer opens on its own, so this button is the
 * cue: admins only, only while matches wait, counting comics rather than
 * questions, and a click opens the dialog.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import OnlineTagReviewButton from "@/components/online-tag/review-button.vue";
import vuetify from "@/plugins/vuetify";
import { useOnlineTagStore } from "@/stores/online-tag";

const SERIES_PROMPT = {
  fingerprint: "a",
  pk: 1,
  comics: [{ pk: 1 }, { pk: 2 }, { pk: 3 }],
};

function mountButton({
  isStaff = true,
  pendingPrompts = [SERIES_PROMPT],
} = {}) {
  const pinia = createTestingPinia({
    stubActions: false,
    initialState: {
      auth: { user: { isStaff } },
      onlineTag: { pendingPrompts },
    },
  });
  const wrapper = mount(OnlineTagReviewButton, {
    global: { plugins: [vuetify, pinia] },
  });
  return { wrapper, store: useOnlineTagStore(pinia) };
}

describe("OnlineTagReviewButton", () => {
  test("hidden for non-admins", () => {
    const { wrapper } = mountButton({ isStaff: false });

    expect(wrapper.find(".reviewButton").exists()).toBe(false);
  });

  test("hidden while nothing waits for review", () => {
    const { wrapper } = mountButton({ pendingPrompts: [] });

    expect(wrapper.find(".reviewButton").exists()).toBe(false);
  });

  test("counts every comic a series-level prompt covers", () => {
    const { wrapper } = mountButton();

    const button = wrapper.find(".reviewButton");
    expect(button.text()).toContain("Review");
    expect(button.text()).toContain("3");
    expect(button.attributes("aria-label")).toBe(
      "Review 3 online tagging matches",
    );
  });

  test("click opens the Match Review dialog", async () => {
    const { wrapper, store } = mountButton();

    await wrapper.find(".reviewButton").trigger("click");

    expect(store.promptDialogOpen).toBe(true);
  });

  test("phones get the icon and count only", () => {
    const { wrapper } = mountButton();

    const word = wrapper.find(".reviewButton .d-none.d-sm-inline");
    expect(word.exists()).toBe(true);
    expect(word.text()).toBe("Review");
  });
});
