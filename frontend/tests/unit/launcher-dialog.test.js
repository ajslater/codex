/*
 * Tests for the unified Online Tagging dialog.
 *
 * One pane: sources, optional per-source pinned ids, and the search controls.
 * A source with a pinned id is fetched by that id; the rest are searched, in
 * one session — so the action button reads "Search", "Tag by ID", or
 * "Tag by ID & Search" depending on how many selected sources are pinned. The
 * id inputs only appear when the selection is a single, id-taggable comic.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

import { HTTP } from "@/api/v4/base";
import OnlineTagLauncherDialog from "@/components/online-tag/launcher-dialog.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";
import { useOnlineTagStore } from "@/stores/online-tag";

// Render the dialog body inline instead of through v-dialog's overlay/teleport
// (which need browser APIs happy-dom lacks). The activator slot is dropped.
const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };

function mountDialog({
  book = { collection: "comics", pk: 7, ids: [7], childCount: 1 },
  taggingDefaults = {
    hasMetronCredentials: true,
    hasComicvineCredentials: true,
    metronKeySet: true,
    comicvineKeySet: true,
  },
  identifiers = [],
} = {}) {
  const pinia = createTestingPinia();
  const wrapper = mount(OnlineTagLauncherDialog, {
    props: { book, identifiers },
    global: {
      plugins: [vuetify, pinia],
      stubs: { VDialog: VDialogStub, RouterLink: true },
    },
  });
  const adminStore = useAdminStore();
  adminStore.taggingDefaults = taggingDefaults;
  const onlineTagStore = useOnlineTagStore();
  return { wrapper, onlineTagStore };
}

describe("OnlineTagLauncherDialog", () => {
  describe("action button", () => {
    test("reads Search when nothing is pinned", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = ["metron", "comicvine"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.actionLabel).toBe("Search");
    });

    test("reads Tag by ID when every selected source is pinned", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = ["metron"];
      wrapper.vm.idInputs = ["metron:12345"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.actionLabel).toBe("Tag by ID");
    });

    test("reads Tag by ID & Search when only some sources are pinned", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = ["metron", "comicvine"];
      wrapper.vm.idInputs = ["metron:12345"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.actionLabel).toBe("Tag by ID & Search");
    });

    test("search is disabled without a selected source", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = [];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.actionDisabled).toBe(true);
    });

    test("an unpinned source is still searchable, so submit stays enabled", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = ["metron"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.actionDisabled).toBe(false);
    });

    test("an id for an unconfigured source blocks submit", async () => {
      const { wrapper } = mountDialog({
        taggingDefaults: {
          hasMetronCredentials: true,
          hasComicvineCredentials: false,
          metronKeySet: true,
        },
      });

      wrapper.vm.sources = ["metron"];
      wrapper.vm.idInputs = ["comicvine:4000-456"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.pinnedIds).toEqual({});
      expect(wrapper.vm.unconfiguredIdWarning).toContain("Comic Vine");
      expect(wrapper.vm.actionDisabled).toBe(true);
    });

    test("disables the action when no source credentials are configured", () => {
      const { wrapper } = mountDialog({
        taggingDefaults: {
          hasMetronCredentials: false,
          hasComicvineCredentials: false,
        },
      });

      expect(wrapper.vm.allSourcesDisabled).toBe(true);
      expect(wrapper.vm.actionDisabled).toBe(true);
    });
  });

  describe("Metron deprecated credentials warning", () => {
    test("warns and links to admin when only a legacy login is stored", async () => {
      const { wrapper } = mountDialog({
        taggingDefaults: {
          hasMetronCredentials: true,
          hasComicvineCredentials: true,
          metronKeySet: false,
        },
      });
      await wrapper.vm.$nextTick();

      const warning = wrapper.find(".credentialWarning");
      expect(warning.text()).toContain(
        "Metron password authentication is deprecated",
      );
      expect(warning.find("router-link-stub").exists()).toBe(true);
    });

    test("stays quiet when Metron is deselected for this session", async () => {
      const { wrapper } = mountDialog({
        taggingDefaults: {
          hasMetronCredentials: true,
          hasComicvineCredentials: true,
          metronKeySet: false,
        },
      });
      wrapper.vm.sources = ["comicvine"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.metronLegacyCredentials).toBe(false);
      expect(wrapper.find(".credentialWarning").exists()).toBe(false);
    });

    test("returns once a pinned Metron id auto-selects Metron", async () => {
      const { wrapper } = mountDialog({
        taggingDefaults: {
          hasMetronCredentials: true,
          hasComicvineCredentials: true,
          metronKeySet: false,
        },
      });
      wrapper.vm.sources = ["comicvine"];
      wrapper.vm.idInputs = ["comicvine:4000-12345"];
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.metronLegacyCredentials).toBe(false);

      wrapper.vm.idInputs = ["metron:12345"];
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.metronLegacyCredentials).toBe(true);
    });

    test("stays quiet once a Metron API key is set", async () => {
      const { wrapper } = mountDialog();
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.metronLegacyCredentials).toBe(false);
      expect(wrapper.find(".credentialWarning").exists()).toBe(false);
    });

    test("stays quiet when Metron is not configured at all", async () => {
      const { wrapper } = mountDialog({
        taggingDefaults: {
          hasMetronCredentials: false,
          hasComicvineCredentials: true,
          comicvineKeySet: true,
        },
      });
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.metronLegacyCredentials).toBe(false);
      expect(wrapper.find(".credentialWarning").exists()).toBe(false);
    });
  });

  describe("idTaggable (whether the id inputs exist)", () => {
    test("true for a single comic", () => {
      const { wrapper } = mountDialog();
      expect(wrapper.vm.idTaggable).toBe(true);
    });

    test("false for a group", () => {
      const { wrapper } = mountDialog({
        book: { collection: "series", pk: 3, ids: [3] },
      });
      expect(wrapper.vm.idTaggable).toBe(false);
    });

    test("false for a multi-comic selection", () => {
      const { wrapper } = mountDialog({
        book: { collection: "comics", ids: [7, 8] },
      });
      expect(wrapper.vm.idTaggable).toBe(false);
    });
  });

  describe("submit", () => {
    test("an unpinned session starts a plain search", async () => {
      const { wrapper, onlineTagStore } = mountDialog();

      wrapper.vm.sources = ["metron"];
      await wrapper.vm.$nextTick();
      await wrapper.vm.submit();

      expect(onlineTagStore.startSession).toHaveBeenCalledWith(
        expect.objectContaining({
          collection: "comics",
          pks: [7],
          sources: ["metron"],
          mode: "auto",
          promptsMode: "ask",
          ids: {},
        }),
      );
    });

    test("submits sources in the admin-configured priority order", async () => {
      const { wrapper, onlineTagStore } = mountDialog();
      const adminStore = useAdminStore();
      adminStore.taggingDefaults = {
        hasMetronCredentials: true,
        hasComicvineCredentials: true,
        defaultSources: ["comicvine", "metron"],
      };

      // Checkbox v-model recorded the clicks metron-first...
      wrapper.vm.sources = ["metron", "comicvine"];
      await wrapper.vm.$nextTick();
      await wrapper.vm.submit();

      // ...but the session is started in the admin's priority order.
      expect(onlineTagStore.startSession).toHaveBeenCalledWith(
        expect.objectContaining({ sources: ["comicvine", "metron"] }),
      );
    });

    test("a mixed session sends the pinned id and both sources", async () => {
      const { wrapper, onlineTagStore } = mountDialog();

      wrapper.vm.sources = ["metron", "comicvine"];
      wrapper.vm.idInputs = ["metron:12345"];
      await wrapper.vm.$nextTick();
      await wrapper.vm.submit();

      expect(onlineTagStore.startSession).toHaveBeenCalledWith(
        expect.objectContaining({
          ids: { metron: "metron:12345" },
          sources: ["metron", "comicvine"],
        }),
      );
      expect(wrapper.emitted("started")).toBeTruthy();
    });

    test("a fully pinned session still goes through startSession", async () => {
      const { wrapper, onlineTagStore } = mountDialog();

      wrapper.vm.sources = ["metron"];
      wrapper.vm.idInputs = ["metron:12345"];
      await wrapper.vm.$nextTick();
      await wrapper.vm.submit();

      expect(onlineTagStore.startSession).toHaveBeenCalledWith(
        expect.objectContaining({ ids: { metron: "metron:12345" } }),
      );
      expect(wrapper.emitted("started")).toBeTruthy();
    });

    test("both sources pinned sends both ids", async () => {
      const { wrapper, onlineTagStore } = mountDialog();

      wrapper.vm.sources = ["metron", "comicvine"];
      wrapper.vm.idInputs = ["metron:12345", "comicvine:4000-456"];
      await wrapper.vm.$nextTick();
      await wrapper.vm.submit();

      expect(onlineTagStore.startSession).toHaveBeenCalledWith(
        expect.objectContaining({
          ids: { metron: "metron:12345", comicvine: "comicvine:4000-456" },
        }),
      );
    });

    test("a stale id can't leak from a selection with no id inputs", async () => {
      const { wrapper, onlineTagStore } = mountDialog({
        book: { collection: "comics", ids: [7, 8], childCount: 2 },
      });

      wrapper.vm.sources = ["metron"];
      wrapper.vm.idInputs = ["metron:12345"];
      await wrapper.vm.$nextTick();
      await wrapper.vm.submit();

      expect(wrapper.vm.idTaggable).toBe(false);
      expect(onlineTagStore.startSession).toHaveBeenCalledWith(
        expect.objectContaining({ ids: {} }),
      );
    });
  });

  describe("pinned ids", () => {
    test("pinning a source that isn't selected selects it", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = ["comicvine"];
      await wrapper.vm.$nextTick();
      wrapper.vm.idInputs = ["metron:12345"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.sources).toContain("metron");
    });

    test("clicking an existing-id chip selects its source", async () => {
      const { wrapper } = mountDialog({
        identifiers: [
          {
            source: "metron",
            type: "comic",
            code: "12345",
            displayName: "Metron",
          },
        ],
      });

      wrapper.vm.sources = ["comicvine"];
      await wrapper.vm.$nextTick();
      wrapper.vm.addId(wrapper.vm.existingOptions[0].value);
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.sources).toContain("metron");
      expect(wrapper.vm.pinnedIds).toEqual({ metron: "metron:12345" });
    });

    test("a bare number pins once its source is picked", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.idInputs = ["12345"];
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.pinnedIds).toEqual({});

      wrapper.vm.sourceChoice = "metron";
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.pinnedIds).toEqual({ metron: "12345" });
    });

    test("only the first id per source is used", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.idInputs = ["metron:12345", "metron:99999"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.pinnedIds).toEqual({ metron: "metron:12345" });
      expect(wrapper.vm.duplicateIdWarning).toContain("Metron");
    });
  });

  describe("search controls with every source pinned", () => {
    test("match mode and prompts are disabled and explain why", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = ["metron"];
      wrapper.vm.idInputs = ["metron:12345"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.searchControlsDisabled).toBe(true);
      expect(wrapper.vm.matchModeHint).toBe(
        "Not used when all sources are tagged by ID.",
      );
      expect(wrapper.vm.promptsModeHint).toBe(
        "Not used when all sources are tagged by ID.",
      );
    });

    test("they come back for a mixed session", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = ["metron", "comicvine"];
      wrapper.vm.idInputs = ["metron:12345"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.searchControlsDisabled).toBe(false);
      expect(wrapper.vm.promptsModeHint).toContain("Pauses on ambiguous");
    });
  });

  describe("id inputs", () => {
    test("offers the comic's Metron / Comic Vine ids as options", () => {
      const { wrapper } = mountDialog({
        identifiers: [
          {
            source: "metron",
            type: "comic",
            code: "12345",
            displayName: "Metron",
          },
          {
            source: "comicvine",
            type: "comic",
            code: "4000-67890",
            displayName: "Comic Vine",
          },
          { source: "gcd", type: "comic", code: "999", displayName: "GCD" },
        ],
      });

      // GCD isn't a taggable source, so it's excluded.
      expect(wrapper.vm.existingOptions.map((o) => o.value)).toEqual([
        "metron:12345",
        "comicvine:4000-67890",
      ]);
    });

    test("excludes non-issue identifiers from the options", () => {
      const { wrapper } = mountDialog({
        identifiers: [
          {
            source: "comicvine",
            type: "publisher",
            code: "4010-1",
            displayName: "Comic Vine",
          },
        ],
      });

      expect(wrapper.vm.existingOptions).toEqual([]);
    });

    test("a bare integer with both sources requires a source pick", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.idInputs = ["12345"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.needsSourceSelect).toBe(true);
      expect(wrapper.vm.needsSourcePick).toBe(true);
      expect(wrapper.vm.actionDisabled).toBe(true);
    });

    test("a bare integer with one configured source needs no pick", async () => {
      const { wrapper } = mountDialog({
        taggingDefaults: {
          hasMetronCredentials: true,
          hasComicvineCredentials: false,
        },
      });

      wrapper.vm.idInputs = ["12345"];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.needsSourceSelect).toBe(false);
      expect(wrapper.vm.needsSourcePick).toBe(false);
      expect(wrapper.vm.pinnedIds).toEqual({ metron: "12345" });
      expect(wrapper.vm.actionDisabled).toBe(false);
    });

    test("only the bare-number chip triggers the source select", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.idInputs = ["https://metron.cloud/issue/12345/"];
      await wrapper.vm.$nextTick();
      // A URL self-identifies, so no manual source needed.
      expect(wrapper.vm.needsSourceSelect).toBe(false);

      wrapper.vm.idInputs = ["54321"];
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.needsSourceSelect).toBe(true);
    });

    test("a pasted pair splits into one chip per source", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.setIdInputs(["metron:12345 comicvine:4000-456"]);
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.idInputs).toEqual([
        "metron:12345",
        "comicvine:4000-456",
      ]);
      expect(wrapper.vm.pinnedSources).toEqual(["metron", "comicvine"]);
    });
  });

  describe("merge all sources", () => {
    test("defaults the search checkbox from the admin tagging default on open", async () => {
      const { wrapper } = mountDialog({
        taggingDefaults: {
          hasMetronCredentials: true,
          hasComicvineCredentials: true,
          defaultSources: ["metron", "comicvine"],
          mergeAllSources: true,
        },
      });
      vi.spyOn(HTTP, "post").mockResolvedValue({ data: {} });

      // Data default is off; opening the dialog seeds it from the admin default.
      expect(wrapper.vm.mergeAllSources).toBe(false);
      await wrapper.vm.initFromDefaults();

      expect(wrapper.vm.mergeAllSources).toBe(true);
      expect(wrapper.vm.canMerge).toBe(true);
    });

    test("passes mergeAllSources through startSession", async () => {
      const { wrapper, onlineTagStore } = mountDialog();

      wrapper.vm.activeTab = "search";
      wrapper.vm.sources = ["metron", "comicvine"];
      wrapper.vm.mergeAllSources = true;
      await wrapper.vm.$nextTick();
      await wrapper.vm.submit();

      expect(onlineTagStore.startSession).toHaveBeenCalledWith(
        expect.objectContaining({ mergeAllSources: true }),
      );
    });

    test("is enabled only with two or more sources selected", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.activeTab = "search";
      wrapper.vm.sources = ["metron", "comicvine"];
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.canMerge).toBe(true);

      wrapper.vm.sources = ["metron"];
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.canMerge).toBe(false);
    });

    test("sums per-source calls when merging two sources", async () => {
      const { wrapper } = mountDialog({
        book: { collection: "series", pk: 3, ids: [3], childCount: 10 },
      });

      wrapper.vm.activeTab = "search";
      wrapper.vm.sources = ["metron", "comicvine"];
      await wrapper.vm.$nextTick();
      // First-match-wins bills the costliest source: max(metron 2, comicvine
      // auto 3) = 3 calls/comic x 10 comics.
      expect(wrapper.vm.totalCalls).toBe(30);

      wrapper.vm.mergeAllSources = true;
      await wrapper.vm.$nextTick();
      // Merge sums per-source calls: (metron 2 + comicvine 3) x 10 comics.
      expect(wrapper.vm.totalCalls).toBe(50);
    });
  });

  describe("match mode hint", () => {
    test("appends the Comic Vine request count when Comic Vine is active", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = ["metron", "comicvine"];
      wrapper.vm.matchMode = "auto";
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.matchModeHint).toContain(
        "~3 Comic Vine requests/comic.",
      );
    });

    test("omits the request-count tail on a Metron-only run", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.sources = ["metron"];
      wrapper.vm.matchMode = "careful";
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.matchModeHint).toContain("high-confidence");
      expect(wrapper.vm.matchModeHint).not.toContain("requests/comic");
    });
  });
});

export default {};
