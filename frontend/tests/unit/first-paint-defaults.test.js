/*
 * First paint follows the admin's site defaults.
 *
 * ``browser.vue`` and ``reader.vue`` run ``created()`` before ``/session``
 * resolves on a cold boot, so they seed from a watcher on the auth store's
 * ``defaults`` instead. The seed stops once the session's own settings load:
 * a later ``/session`` refetch with the same ``defaultsRev`` must never
 * overwrite them.
 */
import { createTestingPinia } from "@pinia/testing";
import { shallowMount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

vi.mock(import("@/api/v4/auth"), async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, getSession: vi.fn() };
});

import * as API from "@/api/v4/auth";
import MainBrowser from "@/browser.vue";
import vuetify from "@/plugins/vuetify";
import MainReader from "@/reader.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useReaderStore } from "@/stores/reader";

const DEFAULTS = Object.freeze({
  browser: {
    topCollection: "folders",
    show: { publishers: true, imprints: true, series: true, volumes: false },
    orderBy: "",
    orderReverse: false,
    viewMode: "table",
    twentyFourHourTime: true,
    alwaysShowFilename: false,
    bookmark: "UNREAD",
    tableColumns: { folders: ["cover", "name"] },
  },
  reader: {
    fitTo: "H",
    readingDirection: "rtl",
    twoPages: false,
    pageTransition: true,
    cacheBook: false,
  },
});

function mountView(component, stubActions) {
  const pinia = createTestingPinia({
    stubActions,
    initialState: { auth: { adminFlags: { nonUsers: true } } },
  });
  shallowMount(component, { global: { plugins: [pinia, vuetify] } });
  return useAuthStore();
}

async function refetchSession(auth) {
  API.getSession.mockResolvedValue({
    data: {
      adminFlags: { nonUsers: true },
      defaults: structuredClone(DEFAULTS),
      defaultsRev: auth.defaultsRev,
    },
  });
  await auth.loadAdminFlags();
}

describe("browser first paint", () => {
  test("seeds the site defaults once /session resolves", async () => {
    const auth = mountView(MainBrowser, ["loadSettings", "loadBrowserPage"]);
    const store = useBrowserStore();
    expect(store.settings.topCollection).toBe("publishers");

    auth.defaults = structuredClone(DEFAULTS);
    auth.defaultsRev = "r1";
    await vi.waitFor(() => {
      expect(store.settings.topCollection).toBe("folders");
    });
    expect(store.settings.viewMode).toBe("table");
    expect(store.settings.show.imprints).toBe(true);
    expect(store.settings.filters.bookmark).toBe("UNREAD");
    expect(store.settings.orderBy).toBe("sort_name");
    expect(store._resolveTableColumns()).toEqual(["cover", "name"]);
  });

  test("a refetch with the same revision leaves loaded settings alone", async () => {
    const auth = mountView(MainBrowser, ["loadSettings", "loadBrowserPage"]);
    const store = useBrowserStore();
    auth.defaults = structuredClone(DEFAULTS);
    auth.defaultsRev = "r1";
    await vi.waitFor(() => {
      expect(store.settings.topCollection).toBe("folders");
    });

    // The session's own settings land.
    store.browserSettingsLoaded = true;
    store.settings.topCollection = "series";
    await refetchSession(auth);
    await vi.waitFor(() => {
      expect(auth.defaultsRev).toBe("r1");
    });
    expect(store.settings.topCollection).toBe("series");
  });
});

describe("reader first paint", () => {
  test("seeds the global settings until they load", async () => {
    const auth = mountView(MainReader, [
      "loadGlobalSettings",
      "flushBookmarkWrite",
    ]);
    const store = useReaderStore();
    expect(store.globalSettings.fitTo).toBe("W");

    auth.defaults = structuredClone(DEFAULTS);
    auth.defaultsRev = "r1";
    await vi.waitFor(() => {
      expect(store.globalSettings.fitTo).toBe("H");
    });
    expect(store.globalSettings.readingDirection).toBe("rtl");

    // The stored global settings land.
    store._applyGlobalSettings({ fitTo: "S" });
    await refetchSession(auth);
    expect(store.globalSettings.fitTo).toBe("S");
  });
});

export default {};
