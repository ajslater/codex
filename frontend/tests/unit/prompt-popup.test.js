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
    },
    score: 0.91,
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
