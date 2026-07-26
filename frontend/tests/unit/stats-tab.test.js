/*
 * Tests for the Admin Stats tab.
 *
 * The tab is what an administrator sees of the anonymous stats report, so
 * behavior locked in here:
 *   - Every section the API returns is rendered under a titled table.
 *   - Toggle booleans read as Yes/No, and "have you configured this"
 *     booleans read as Set/Not set, so nobody mistakes one for the other.
 *   - The API key is never rendered, even though the payload carries it.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import StatsTab from "@/components/admin/tabs/stats-tab.vue";
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
    orderBy: { sort_name: 2 },
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
  metadata: { characterCount: 609, storyCount: 151 },
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
    mergeAllSources: false,
    defaultSources: { metron: 1, comicvine: 1 },
    hasMetronCredentials: true,
    hasComicvineCredentials: false,
    metronUrlSet: false,
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

const SECTION_TITLES = [
  "Platform",
  "Config",
  "File Types",
  "User Settings",
  "Browser Collections",
  "Tags",
  "Reading",
  "Identifiers",
  "Admin Flags",
  "Online Tagging",
  "Authentication",
  "Email",
  "Rate Limits",
  "Deployment",
];

function mountTab(stats = STATS) {
  const pinia = createTestingPinia({ initialState: { admin: { stats } } });
  return mount(StatsTab, {
    global: { plugins: [pinia, vuetify] },
  });
}

describe("AdminStatsTab", () => {
  test("renders a table for every stats section", () => {
    const text = mountTab().text();
    for (const title of SECTION_TITLES) {
      expect(text).toContain(title);
    }
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

  test("survives a params-filtered response with sections missing", () => {
    // /admin/stats?platform=... returns only the requested sections.
    const wrapper = mountTab({ platform: STATS.platform });
    expect(wrapper.text()).toContain("arm64");
    expect(wrapper.text()).not.toContain("Bookmarks");
  });
});
