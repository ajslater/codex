/*
 * A source the backend lists that the frontend has no descriptor for.
 *
 * tagging-choices.json lists the sources the backend can drive; the copy for
 * each lives in source-labels.js. If the choices ever name a source the UI
 * cannot describe, the Tagging tab and the launcher leave it out instead of
 * breaking: no row, no checkbox, no id chip, and it never counts toward
 * "two or more sources".
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

import TAGGING_CHOICES from "@/choices/tagging-choices.json";
import TaggingTab from "@/components/admin/tabs/tagging-tab.vue";
import OnlineTagLauncherDialog from "@/components/online-tag/launcher-dialog.vue";
import {
  credentialFields,
  sourceLabel,
  SUPPORTED_SOURCES,
} from "@/components/online-tag/source-labels";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";

// Hoisted above the imports, so the literal can't come from a constant.
vi.mock("@/choices/tagging-choices.json", async (importOriginal) => {
  const original = await importOriginal();
  return {
    default: {
      ...original.default,
      sources: [...original.default.sources, "newsource"],
    },
  };
});

const UNDESCRIBED = "newsource";
const DESCRIBED = Object.freeze(["metron", "comicvine", "versedb"]);
const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };

function mountLauncher(configuredSources, identifiers = []) {
  const pinia = createTestingPinia();
  const wrapper = mount(OnlineTagLauncherDialog, {
    props: {
      book: { collection: "comics", pk: 7, ids: [7], childCount: 1 },
      identifiers,
    },
    global: {
      plugins: [vuetify, pinia],
      stubs: { VDialog: VDialogStub, RouterLink: true },
    },
  });
  useAdminStore().taggingDefaults = { configuredSources };
  return wrapper;
}

function mountTab(configuredSources) {
  const pinia = createTestingPinia({
    initialState: {
      admin: {
        taggingDefaults: {
          defaultFormats: ["COMIC_INFO"],
          defaultSources: [...configuredSources],
          configuredSources,
          comicvineUrl: "",
        },
      },
    },
  });
  return mount(TaggingTab, {
    global: {
      plugins: [pinia, vuetify],
      stubs: {
        TagWriteErrorsPanel: true,
        TaggingStatusTable: true,
        ValidationChip: true,
        ConfirmDialog: true,
      },
    },
  });
}

describe("a source with no descriptor", () => {
  test("is listed by the backend but not supported here", () => {
    expect(TAGGING_CHOICES.sources).toContain(UNDESCRIBED);
    expect(SUPPORTED_SOURCES).toEqual(DESCRIBED);
    expect(sourceLabel(UNDESCRIBED)).toBe(UNDESCRIBED);
  });

  test("credential field names follow the backend's columns", () => {
    expect(credentialFields("metron")).toEqual({
      key: "metronKey",
      url: undefined,
    });
    expect(credentialFields("comicvine")).toEqual({
      key: "comicvineKey",
      url: "comicvineUrl",
    });
    expect(credentialFields("versedb")).toEqual({
      key: "versedbKey",
      url: undefined,
    });
  });

  test("gets no row on the Tagging tab", () => {
    const wrapper = mountTab([...DESCRIBED, UNDESCRIBED]);
    expect(wrapper.findAll(".sourceRow")).toHaveLength(DESCRIBED.length);
    expect(wrapper.text()).not.toContain(UNDESCRIBED);
    expect(wrapper.vm.canMerge).toBe(true);
  });

  test("is not offered or counted by the launcher", async () => {
    const wrapper = mountLauncher(
      ["metron", UNDESCRIBED],
      [
        { source: UNDESCRIBED, type: "comic", code: "123", displayName: "V" },
        { source: "metron", type: "comic", code: "456", displayName: "Metron" },
      ],
    );
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.sources).toEqual(DESCRIBED);
    expect(wrapper.vm.sourceItems.map((item) => item.value)).toEqual(DESCRIBED);
    expect(wrapper.vm.configuredSources).toEqual(["metron"]);
    expect(wrapper.vm.multipleConfigured).toBe(false);
    expect(wrapper.vm.soleConfiguredSource).toBe("metron");
    expect(wrapper.vm.existingOptions.map((option) => option.value)).toEqual([
      "metron:456",
    ]);
  });
});
