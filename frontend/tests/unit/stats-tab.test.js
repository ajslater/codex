/*
 * Tests for the Admin Stats tab.
 *
 * The tab is what an administrator sees of the anonymous stats report, so
 * behavior locked in here:
 *   - Every section the component declares is rendered under a titled
 *     table. The titles come from the component so renaming one there
 *     does not leave a stale copy here.
 *   - Toggle booleans read as Yes/No, and "have you configured this"
 *     booleans read as Set/Not set, so nobody mistakes one for the other.
 *   - The API key is never rendered, even though the payload carries it.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import StatsTab, {
  SECTION_TITLES,
} from "@/components/admin/tabs/stats-tab.vue";
import vuetify from "@/plugins/vuetify";

const STATS = {
  platform: {
    docker: false,
    machine: "arm64",
    cores: 10,
    system: { name: "Darwin", release: "25.5.0" },
    pythonVersion: "3.14.4",
    codexVersion: "2.2.3",
  },
  config: {
    libraryCount: 2,
    sessionCount: 1,
    userAnonymousCount: 0,
    userRegisteredCount: 2,
    authGroupCount: 0,
    libraryReadOnlyCount: 1,
    libraryPollCount: 2,
    libraryEventsCount: 2,
    libraryGroupAclCount: 0,
    customCoverCount: 3,
    customCoverUploadedCount: 2,
    customCoverDirCount: 1,
    failedImportCount: 0,
    apiKey: "s3cr3t-api-key",
  },
  sessions: {
    topCollection: { publishers: 2 },
    // camelCase, like the API renders it and like the choices maps are keyed.
    orderBy: { sortName: 2 },
    dynamicCovers: { true: 2 },
    finishOnLastPage: { true: 1 },
    fitTo: { W: 1 },
    readingDirection: { ltr: 1 },
    viewMode: { cover: 2, table: 1 },
    tableCoverSize: { sm: 1 },
    customCovers: { true: 2 },
    multiSortCount: 0,
  },
  collections: {
    publisherCount: 17,
    imprintCount: 20,
    seriesCount: 56,
    volumeCount: 60,
    issueCount: 154,
    folderCount: 70,
    storyArcCount: 23,
  },
  fileTypes: { cbz: 100, cbr: 50, cb7: 2, pdf: 3, unknown: 1 },
  metadata: {
    characterCount: 609,
    storyCount: 151,
    creditPersonCount: 40,
    creditPrimaryCount: 4,
    reprintCount: 6,
    reprintAlternativeNameCount: 2,
    comicMangaVolumeCount: 3,
    comicUrlsCount: 12,
    comicMangaYesCount: 5,
    comicMangaNoCount: 140,
    comicMangaUnknownCount: 9,
  },
  perUser: {
    browserUserCount: 2,
    readerUserCount: 2,
    readerScopedUserCount: 1,
    browserOrderByUsers: { sortName: 1, "": 1 },
    browserChosenOrderByUsers: { sortName: 1 },
    readerGlobalFitToUsers: { W: 1, "": 1 },
  },
  usage: {
    bookmarkCount: 1,
    favoriteCount: 4,
    favoriteUserCount: 1,
    favorites: { comics: 4 },
  },
  identifiers: { "metron:comic": 85, "comicvine:comic": 126 },
  adminFlags: {
    autoUpdate: false,
    folderView: true,
    sendTelemetry: true,
    apiKeySet: true,
    bannerTextSet: false,
    browserDefaultCollection: "publishers",
    browserMaxObjPerPage: 100,
    ageRatingDefault: "Everyone",
  },
  tagging: {
    defaultMatchMode: "auto",
    defaultEffort: "balanced",
    mergeAllSources: false,
    defaultSources: { metron: 1, comicvine: 1 },
    hasMetronCredentials: true,
    hasComicvineCredentials: false,
    comicvineUrlSet: false,
  },
  auth: {
    oidcEnabled: false,
    oidcPkce: true,
    oidcScopeCustom: false,
    oidcTokenAuthMethod: "",
    userAgeCeilingCount: 0,
  },
  email: { smtpConfigured: false, smtpUseTls: true, smtpUseSsl: false },
  throttle: { throttleAnon: 0, throttleResetPassword: 5 },
  deployment: {
    remoteUserAuth: false,
    failedLoginLog: true,
    urlPathPrefixSet: true,
  },
};

function mountTab(stats = STATS) {
  const pinia = createTestingPinia({ initialState: { admin: { stats } } });
  return mount(StatsTab, {
    global: { plugins: [pinia, vuetify] },
  });
}

describe("AdminStatsTab", () => {
  test("renders a table for every stats section", () => {
    const captions = mountTab()
      .findAll(".adminKvCaption")
      .map((caption) => caption.text());
    // The whole ordered list, not per-title containment: a section that stops
    // rendering, one rendered twice, and an empty title all have to fail here,
    // which a loop of toContain over titles taken from the component cannot.
    expect(captions).toStrictEqual([...SECTION_TITLES]);
  });

  test("never renders the api key", () => {
    const text = mountTab().text();
    expect(text).not.toContain("s3cr3t-api-key");
    // Its presence is still reported, without the value.
    expect(text).toContain("API Key");
  });

  test("toggles read as Yes/No", () => {
    const text = mountTab().text();
    expect(text).toContain("Folder View");
    expect(text).toContain("Yes");
    expect(text).toContain("No");
  });

  test("configured-or-not booleans read as Set/Not set", () => {
    const text = mountTab().text();
    expect(text).toContain("Set");
    expect(text).toContain("Not set");
  });

  test("renders new v2 sections with readable labels", () => {
    const text = mountTab().text();
    expect(text).toContain("Read Only");
    expect(text).toContain("Bookmarks");
    expect(text).toContain("Single Sign On");
    expect(text).toContain("Reverse Proxy Subpath");
    expect(text).toContain("Metron Credentials");
  });

  test("renders identifier buckets as source and type", () => {
    expect(mountTab().text()).toContain("Metron: Comic");
  });

  test("labels bucket keys instead of showing them raw", () => {
    // The choices maps are camelCased, so case-converting a key found nothing
    // and Order By rendered "sortName" while Fit To rendered "W".
    const text = mountTab().text();
    expect(text).toContain("Name");
    expect(text).not.toContain("sortName");
    expect(text).not.toContain("fitTo");
  });

  test("boolean buckets read as on and off", () => {
    // They arrive as the strings "true"/"false", which is the wire's word for
    // the value and not a reader's.
    const text = mountTab().text();
    expect(text).toContain("On");
    expect(text).not.toContain("true");
  });

  test("fills the per-user table from the camelCased payload", () => {
    // The section arrives as perUser, not per_user; reading the snake_case
    // name rendered the caption over an empty table.
    const text = mountTab().text();
    expect(text).toContain("Browser User");
    expect(text).toContain("Unset (Name)");
  });

  test("every section that has data renders rows", () => {
    // The empty per-user table was invisible because nothing asserted that a
    // populated section actually produces rows.
    const wrapper = mountTab();
    const blocks = wrapper.findAll(".adminKvBlock");
    expect(blocks.length).toBe(SECTION_TITLES.length);
    for (const block of blocks) {
      expect(block.findAll("tr").length).toBeGreaterThan(0);
    }
  });

  test("renders the 2.3.0 counts and the tagging effort", () => {
    const text = mountTab().text();
    expect(text).toContain("Reprints");
    expect(text).toContain("Comics with Web Links");
    expect(text).toContain("Manga Unknown");
    expect(text).toContain("Effort");
  });

  test("indents rows that detail the row above them", () => {
    // The indent set held plural spellings that matched no payload key, so
    // these rendered flat. The leading "+" is a marker the table strips, so
    // the class is what says whether it worked.
    const indented = mountTab()
      .findAll("td.indent")
      .map((cell) => cell.text());
    expect(indented).toContain("Persons");
    expect(indented).toContain("Primaries");
    expect(indented).toContain("Alternative Names");
  });

  test("survives a params-filtered response with sections missing", () => {
    // /admin/stats?platform=... returns only the requested sections.
    const wrapper = mountTab({ platform: STATS.platform });
    expect(wrapper.text()).toContain("arm64");
    expect(wrapper.text()).not.toContain("Bookmarks");
  });
});
