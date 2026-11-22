/*
 * VerseDB, the third online tagging source, across the UI.
 *
 * Behavior locked in here:
 *   - The Tagging tab shows a VerseDB card: its token link, its free-tier
 *     budget and terms. Saving its first key enables it last in priority,
 *     and three enabled sources can merge.
 *   - The launcher reads `versedb:ID` and versedb.com urls as VerseDB, asks
 *     which source a bare id is among all three, warns on VerseDB's hourly
 *     and daily caps, and says which sources ignore effort.
 *   - The review dialog credits VerseDB under its candidates, from the
 *     choices map, so a prompt cached before the credit existed shows it.
 *   - The status strip labels the source and shows its hourly budget.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import TaggingStatusTable from "@/components/admin/tabs/tagging-status-table.vue";
import TaggingTab from "@/components/admin/tabs/tagging-tab.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import OnlineTagLauncherDialog from "@/components/online-tag/launcher-dialog.vue";
import OnlineTagPromptPopup from "@/components/online-tag/prompt-popup.vue";
import { NUMBER_FORMAT } from "@/datetime";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";
import { useOnlineTagStore } from "@/stores/online-tag";

const ALL = Object.freeze(["metron", "comicvine", "versedb"]);
const CREDIT = "Data from VerseDB";
const CREDIT_URL = "https://versedb.com";
const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };
const fmt = (n) => NUMBER_FORMAT.format(n);

function mountTab(overrides = {}) {
  const taggingDefaults = {
    defaultFormats: ["COMIC_INFO"],
    deleteOriginal: false,
    defaultMatchMode: "auto",
    defaultPromptsMode: "ask",
    defaultSources: [],
    configuredSources: [],
    comicvineUrl: "",
    ...overrides,
  };
  const pinia = createTestingPinia({
    initialState: { admin: { taggingDefaults } },
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

const panelFor = (wrapper) =>
  wrapper
    .findAll(".sourcePanel")
    .find((panel) => panel.find(".adminCardTitle").text() === "VerseDB");

describe("Tagging tab — VerseDB card", () => {
  test("shows its token link, budget and terms", () => {
    const panel = panelFor(mountTab());
    expect(panel).toBeTruthy();
    const link = panel.find(".adminHint a");
    expect(link.attributes("href")).toBe(
      "https://versedb.com/my/apps/custom/create",
    );
    const notes = panel.find(".sourceNotes").text();
    expect(notes).toContain(
      `Free tier: ${fmt(300)} requests an hour and ${fmt(4000)} a day, about 3 per comic.`,
    );
    expect(notes).toContain("Non-commercial use only.");
    // The budget line already says "Free tier"; the terms do not repeat it.
    expect(notes.match(/Free/gv)).toHaveLength(1);
    expect(notes).toContain("Metron and Comic Vine win");
    // A settings card shows none of VerseDB's data, so it carries no credit.
    expect(panel.text()).not.toContain(CREDIT);
    // No mirror exists, so no custom url field.
    expect(panel.text()).not.toContain("Custom URL");
  });

  test("its first key enables it last in priority", async () => {
    const wrapper = mountTab({
      configuredSources: ["metron", "comicvine"],
      defaultSources: ["comicvine", "metron"],
    });
    const vm = wrapper.vm;
    const store = useAdminStore();
    store.updateTaggingDefaults.mockImplementation(() => {
      store.taggingDefaults = {
        ...store.taggingDefaults,
        configuredSources: ALL,
      };
    });

    vm.keys.versedb = "token";
    await vm.saveCredentials("versedb");
    await vm.$nextTick();

    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      versedbKey: "token",
    });
    expect(vm.draft.defaultSources).toEqual(["comicvine", "metron", "versedb"]);
    expect(vm.sourceRowStyle("versedb")).toEqual({ order: 2 });
    expect(vm.canMerge).toBe(true);
  });

  test("its clear dialog removes the key alone", async () => {
    const wrapper = mountTab({ configuredSources: ["versedb"] });
    const store = useAdminStore();
    wrapper.vm.clearCredentials("versedb");
    expect(store.updateTaggingDefaults).toHaveBeenCalledWith({
      versedbKey: "",
    });

    await panelFor(wrapper).find(".v-expansion-panel-title").trigger("click");
    await new Promise((resolve) => setTimeout(resolve, 0));
    const dialog = wrapper
      .findAllComponents(ConfirmDialog)
      .find((d) => d.props("titleText") === "Clear VerseDB API Key");
    expect(dialog.props("text")).toBe("Remove the saved VerseDB API key?");
  });

  test("the effort hint says Metron and VerseDB ignore it", () => {
    expect(mountTab().text()).toContain("Metron and VerseDB ignore this.");
  });
});

function mountLauncher({ configured = ALL, childCount = 1, collection } = {}) {
  const pinia = createTestingPinia();
  const book = collection
    ? { collection, pk: 3, ids: [3], childCount }
    : { collection: "comics", pk: 7, ids: [7], childCount };
  const wrapper = mount(OnlineTagLauncherDialog, {
    props: { book, identifiers: [] },
    global: {
      plugins: [vuetify, pinia],
      stubs: { VDialog: VDialogStub, RouterLink: true },
    },
  });
  useAdminStore().taggingDefaults = { configuredSources: [...configured] };
  return wrapper;
}

describe("Launcher — VerseDB", () => {
  test("versedb:ID and a versedb.com url self-identify", () => {
    const { vm } = mountLauncher();
    expect(vm.detectSource("versedb:123")).toBe("versedb");
    expect(vm.detectSource("https://versedb.com/issue/1215061/slug")).toBe(
      "versedb",
    );
  });

  test("a pasted VerseDB id pins VerseDB", async () => {
    const wrapper = mountLauncher();
    wrapper.vm.idInputs = ["versedb:1215061"];
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.pinnedIds).toEqual({ versedb: "versedb:1215061" });
  });

  test("a bare id asks among all three", async () => {
    const wrapper = mountLauncher();
    wrapper.vm.idInputs = ["12345"];
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.needsSourcePick).toBe(true);
    expect(wrapper.text()).toContain(
      "Bare ID — choose Metron, Comic Vine, or VerseDB.",
    );
    expect(wrapper.vm.sourceChoices.map((choice) => choice.title)).toEqual([
      "Auto-detect",
      "Metron",
      "Comic Vine",
      "VerseDB",
    ]);
  });

  test("one, two and three configured sources", () => {
    const one = mountLauncher({ configured: ["versedb"] }).vm;
    expect(one.soleConfiguredSource).toBe("versedb");
    expect(one.multipleConfigured).toBe(false);

    const two = mountLauncher({ configured: ["metron", "versedb"] }).vm;
    expect(two.multipleConfigured).toBe(true);
    expect(two.sourceItems.find((i) => i.value === "comicvine").disabled).toBe(
      true,
    );

    const three = mountLauncher().vm;
    expect(three.sourceItems.every((item) => !item.disabled)).toBe(true);
  });

  test("the rate warning uses VerseDB's hourly cap", async () => {
    const wrapper = mountLauncher({ collection: "series", childCount: 200 });
    wrapper.vm.sources = ["versedb"];
    await wrapper.vm.$nextTick();
    // 200 comics x 3 requests = 600, over 300 an hour, under 4000 a day.
    expect(wrapper.vm.rateLimitWarning).toBe(
      "Will be rate-limited by: VerseDB (300/hr limit)",
    );
  });

  test("the rate warning uses VerseDB's daily cap", async () => {
    const wrapper = mountLauncher({ collection: "series", childCount: 2000 });
    wrapper.vm.sources = ["versedb"];
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.rateLimitWarning).toBe(
      "Will be rate-limited by: VerseDB (4000/day limit)",
    );
  });

  test("the effort hint names the active sources that ignore effort", async () => {
    const wrapper = mountLauncher();
    wrapper.vm.sources = [...ALL];
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.effortHint).toContain("Comic Vine requests/comic.");
    expect(wrapper.vm.effortHint).toContain("Metron and VerseDB ignore it.");

    wrapper.vm.sources = ["versedb"];
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.effortHint).toContain("VerseDB ignores it.");
    expect(wrapper.vm.effortHint).not.toContain("requests/comic");
  });
});

function mountPopup(source) {
  const pinia = createTestingPinia();
  const wrapper = mount(OnlineTagPromptPopup, {
    global: { plugins: [vuetify, pinia], stubs: { VDialog: VDialogStub } },
  });
  const store = useOnlineTagStore();
  store.pendingPrompts = [
    {
      fingerprint: "fp1",
      pk: 7,
      path: "/comics/a.cbz",
      source,
      candidates: [
        {
          source,
          issueId: 1_215_061,
          summary: { series: "S", issue: "1", year: 2020, coverUrl: "" },
          score: 0.9,
          url: "",
        },
      ],
    },
  ];
  store.promptDialogOpen = true;
  return wrapper;
}

describe("Review dialog — VerseDB credit", () => {
  test("a VerseDB prompt credits VerseDB under its candidates", async () => {
    const wrapper = mountPopup("versedb");
    await wrapper.vm.$nextTick();
    await wrapper.find(".v-expansion-panel-title").trigger("click");
    await new Promise((resolve) => setTimeout(resolve, 0));
    const credit = wrapper.find(".promptCredit a");
    expect(credit.text()).toBe(CREDIT);
    expect(credit.attributes("href")).toBe(CREDIT_URL);
  });

  test("a Metron prompt carries no credit", async () => {
    const wrapper = mountPopup("metron");
    await wrapper.vm.$nextTick();
    await wrapper.find(".v-expansion-panel-title").trigger("click");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(wrapper.find(".promptCredit").exists()).toBe(false);
  });
});

describe("Status strip — VerseDB", () => {
  test("labels the source and shows its hourly budget", () => {
    const pinia = createTestingPinia({
      initialState: {
        onlineTag: {
          snapshot: {
            sessionId: "sid",
            active: true,
            batch: {
              total: 1,
              completed: 0,
              matched: 0,
              needsReview: 0,
              noMatch: 0,
              error: 0,
              queued: 1,
              sources: ["versedb"],
              matchMode: "auto",
              mergeAllSources: false,
              etaEpoch: null,
            },
            sources: [
              {
                source: "versedb",
                ratePerMinute: 5,
                rateLimited: false,
                retryAtEpoch: null,
                budgetWindow: "hour",
                sustainedLimit: 300,
                sustainedRemaining: 287,
              },
            ],
            comics: [],
            comicCount: 1,
            shownCount: 0,
          },
          pendingPrompts: [],
          promptDialogOpen: false,
          locallyResolved: {},
        },
      },
    });
    const wrapper = mount(TaggingStatusTable, {
      global: {
        plugins: [pinia, vuetify],
        stubs: { ConfirmDialog: true },
      },
    });
    const text = wrapper.text();
    expect(text).toContain("VerseDB");
    expect(text).toContain(`${fmt(287)}/${fmt(300)} hour`);
  });
});
