/*
 * Tests for the unified Online Tagging dialog.
 *
 * One dialog with two expansion panels: "Search" (filename search + match)
 * and "By ID" (exact issue id). Only one panel opens at a time; the action
 * button reads "Search" or "Tag" depending on the open panel; the By ID panel
 * only exists when the selection is a single, id-taggable comic.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

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
    test("reads Search on the search panel and Tag on the By ID panel", async () => {
      const { wrapper } = mountDialog();

      expect(wrapper.vm.actionLabel).toBe("Search");

      wrapper.vm.activeTab = "byId";
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.actionLabel).toBe("Tag");
    });

    test("search is disabled without a selected source", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.activeTab = "search";
      wrapper.vm.sources = [];
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.actionDisabled).toBe(true);
    });

    test("By ID is disabled until an identifier is entered", async () => {
      const { wrapper } = mountDialog();

      wrapper.vm.activeTab = "byId";
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.actionDisabled).toBe(true);

      wrapper.vm.identifier = "metron:12345";
      await wrapper.vm.$nextTick();
      expect(wrapper.vm.actionDisabled).toBe(false);
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

  describe("idTaggable (whether the By ID panel exists)", () => {
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

  describe("Search panel", () => {
    test("submit starts a tagging session", async () => {
      const { wrapper, onlineTagStore } = mountDialog();

      wrapper.vm.activeTab = "search";
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
        }),
      );
      expect(onlineTagStore.tagById).not.toHaveBeenCalled();
    });
  });

  describe("By ID panel", () => {
    test("submit tags by id", async () => {
      const { wrapper, onlineTagStore } = mountDialog();
      onlineTagStore.tagById.mockResolvedValue({ source: "metron", id: 12345 });

      wrapper.vm.activeTab = "byId";
      wrapper.vm.identifier = "metron:12345";
      await wrapper.vm.$nextTick();
      await wrapper.vm.submit();

      expect(onlineTagStore.tagById).toHaveBeenCalledWith({
        collection: "comics",
        pk: 7,
        identifier: "metron:12345",
        source: "",
      });
      expect(onlineTagStore.startSession).not.toHaveBeenCalled();
    });

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

      wrapper.vm.activeTab = "byId";
      wrapper.vm.identifier = "12345";
      await wrapper.vm.$nextTick();

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

      wrapper.vm.activeTab = "byId";
      wrapper.vm.identifier = "12345";
      await wrapper.vm.$nextTick();

      expect(wrapper.vm.needsSourcePick).toBe(false);
      expect(wrapper.vm.actionDisabled).toBe(false);
    });

    test("selecting an existing id fills the field and submits it", async () => {
      const { wrapper, onlineTagStore } = mountDialog({
        identifiers: [
          {
            source: "metron",
            type: "comic",
            code: "12345",
            displayName: "Metron",
          },
        ],
      });
      onlineTagStore.tagById.mockResolvedValue({ source: "metron", id: 12345 });

      wrapper.vm.activeTab = "byId";
      // The chip's @click sets identifier to the option value.
      wrapper.vm.identifier = wrapper.vm.existingOptions[0].value;
      await wrapper.vm.submit();

      expect(onlineTagStore.tagById).toHaveBeenCalledWith({
        collection: "comics",
        pk: 7,
        identifier: "metron:12345",
        source: "",
      });
    });
  });
});

export default {};
