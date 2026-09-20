/*
 * Tests for the Online Tagging match-review popup.
 *
 * Comicbox scores candidates against reprint series names, so a comic filed
 * under a localized title matches a canonical series that looks nothing like
 * its filename. The popup shows those aliases so the match is explicable, and
 * a pick carries the candidate's volume id so the apply replay can narrow to
 * that volume.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import OnlineTagPromptPopup from "@/components/online-tag/prompt-popup.vue";
import vuetify from "@/plugins/vuetify";
import { useOnlineTagStore } from "@/stores/online-tag";

// Render the dialog body inline instead of through v-dialog's overlay/teleport
// (which need browser APIs happy-dom lacks).
const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };
// Dismiss, Skip All, Pause.
const THREE_HEADER_BUTTONS = 3;

function candidate(overrides = {}) {
  return {
    source: "comicvine",
    issueId: 42,
    summary: {
      series: "Captain Science",
      issue: "1",
      year: 1950,
      publisher: "Youthful",
      coverUrl: "",
      altSeries: [],
      volume: null,
    },
    score: 0.91,
    metadataScore: 1,
    coverScore: 0.6,
    coverHashAttempted: true,
    url: "",
    volumeId: null,
    ...overrides,
  };
}

function mountPopup(candidates) {
  const pinia = createTestingPinia();
  const wrapper = mount(OnlineTagPromptPopup, {
    global: {
      plugins: [vuetify, pinia],
      stubs: { VDialog: VDialogStub },
    },
  });
  const store = useOnlineTagStore();
  store.pendingPrompts = [
    {
      fingerprint: "fp1",
      pk: 7,
      path: "/comics/kapitan.cbz",
      source: "comicvine",
      candidates,
    },
  ];
  store.promptDialogOpen = true;
  return { wrapper, store };
}

describe("OnlineTagPromptPopup", () => {
  describe("reprint series names", () => {
    test("shows the aliases that explain an off-filename match", async () => {
      const { wrapper } = mountPopup([
        candidate({
          summary: {
            ...candidate().summary,
            altSeries: ["Kapitän Wissenschaft", "Capitan Sciencia"],
          },
        }),
      ]);
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain(
        "a.k.a. Kapitän Wissenschaft, Capitan Sciencia",
      );
    });

    test("omits the line when the source carries no aliases", async () => {
      const { wrapper } = mountPopup([candidate()]);
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).not.toContain("a.k.a.");
    });

    test("omits the line for a prompt cached before aliases existed", async () => {
      const summary = { ...candidate().summary };
      delete summary.altSeries;
      const { wrapper } = mountPopup([candidate({ summary })]);
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).not.toContain("a.k.a.");
    });
  });

  /*
   * One prompt stands for a whole series, so the dialog has to say what a
   * pick will actually write — a "Pick" that silently tags twelve comics is
   * not the same promise as one that tags the file it names.
   */
  describe("the comics a pick covers", () => {
    test("says how many more of the series the pick will write", async () => {
      const { wrapper, store } = mountPopup([candidate()]);
      store.pendingPrompts[0].comics = [
        { pk: 7, path: "/comics/kapitan 1.cbz" },
        { pk: 8, path: "/comics/kapitan 2.cbz" },
        { pk: 9, path: "/comics/kapitan 3.cbz" },
      ];
      await wrapper.vm.$nextTick();

      const text = wrapper.text();
      expect(text).toContain("+ 2 more of this series");
      expect(text).toContain("Applies to 3 comics");
      expect(text).toContain("kapitan 2.cbz");
    });

    test("says nothing extra for a prompt covering one comic", async () => {
      const { wrapper } = mountPopup([candidate()]);
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).not.toContain("more of this series");
      expect(wrapper.text()).not.toContain("Applies to");
    });

    test("names only the first few and counts the rest", () => {
      const { wrapper } = mountPopup([candidate()]);
      const prompt = {
        comics: [1, 2, 3, 4, 5].map((n) => ({ pk: n, path: `/c/${n}.cbz` })),
      };

      expect(wrapper.vm.coveredNames(prompt)).toBe(
        "1.cbz, 2.cbz, 3.cbz and 2 more",
      );
    });
  });

  describe("the empty queue", () => {
    test("says the queue is empty instead of spinning forever", async () => {
      const { wrapper, store } = mountPopup([candidate()]);
      store.pendingPrompts = [];
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain("No matches need review.");
      expect(wrapper.findAll(".v-progress-circular")).toHaveLength(0);
    });
  });

  describe("pick", () => {
    test("passes the chosen candidate's volume id", () => {
      const { wrapper, store } = mountPopup([
        candidate(),
        candidate({ volumeId: 9876 }),
      ]);

      wrapper.vm.pick(store.pendingPrompts[0], 1);

      expect(store.resolvePrompt).toHaveBeenCalledWith(
        "fp1",
        "choose",
        1,
        9876,
      );
    });

    test("passes null when the source exposes no volume id", () => {
      const { wrapper, store } = mountPopup([candidate()]);

      wrapper.vm.pick(store.pendingPrompts[0], 0);

      expect(store.resolvePrompt).toHaveBeenCalledWith(
        "fp1",
        "choose",
        0,
        null,
      );
    });
  });
});

export default {};

describe("OnlineTagPromptPopup header", () => {
  test("the title yields and the buttons never shrink", () => {
    // Vuetify's .v-card-title is nowrap + overflow:hidden, so as a flex
    // container it clipped the tail of its last child — the Pause
    // button, in the report (#854).
    const { wrapper } = mountPopup([candidate()]);

    const title = wrapper.find(".v-card-title span");
    expect(title.classes()).toContain("text-truncate");
    expect(title.classes()).toContain("flex-grow-1");
    const actions = wrapper.find(".v-card-title .flex-shrink-0");
    expect(actions.exists()).toBe(true);
    expect(actions.findAll("button").length).toBe(THREE_HEADER_BUTTONS);
  });
});
