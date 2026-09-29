/*
 * "Clear Filters and Search" on the empty browser page
 * (``components/browser/empty.vue`` → ``clearFilters(true)``).
 *
 * Entering a search sends the browser down to the bare root of
 * ``lowestShownCollection`` (e.g. ``/series``). Clearing the search must
 * come back up to the top, as clearing it from the search box does: a bare
 * nav-collection root below the top collection has no breadcrumbs, so the
 * user would be stranded there.
 *
 * Real Vuetify renders the action button; the store's actions run for
 * real, with the router and the browser API mocked.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

vi.mock("@/plugins/router", () => ({
  default: {
    currentRoute: { value: { params: {}, query: {} } },
    push: vi.fn(() => Promise.resolve()),
  },
}));

vi.mock("@/api/v4/browser", async (importOriginal) => ({
  ...(await importOriginal()),
  getBrowserPage: vi.fn(() => Promise.resolve({ data: { breadcrumbs: [] } })),
  resetSettings: vi.fn(),
  updateSettings: vi.fn(),
}));

import * as API from "@/api/v4/browser";
import BrowserEmptyResults from "@/components/browser/empty.vue";
import router from "@/plugins/router";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

// What the settings reset hands back: the site defaults.
const RESET = Object.freeze({
  filters: { bookmark: "" },
  search: "",
  orderBy: "sort_name",
  orderReverse: false,
  collectionOrderMemory: {},
});

const setRoute = (collection, parentIds) => {
  router.currentRoute.value = {
    params: parentIds ? { collection, parentIds } : { collection },
    query: {},
  };
};

const wrappers = [];

const mountEmpty = (search) => {
  const pinia = createTestingPinia({
    stubActions: false,
    initialState: {
      auth: { user: { pk: 1 } },
      browser: {
        page: { librariesExist: true },
        settings: {
          // A non-default filter is what shows the action button.
          filters: { bookmark: "UNREAD" },
          orderBy: search ? "search_score" : "sort_name",
          search,
          // volumes hidden -> lowestShownCollection resolves to "series"
          show: {
            publishers: true,
            imprints: true,
            series: true,
            volumes: false,
          },
          topCollection: "publishers",
        },
      },
    },
  });
  const wrapper = mount(BrowserEmptyResults, {
    global: { plugins: [pinia, vuetify] },
  });
  wrappers.push(wrapper);
  return { wrapper, store: useBrowserStore() };
};

const clickClear = async (wrapper) => {
  const button = wrapper.find("button");
  expect(button.text()).toBe("Clear Filters and Search");
  await button.trigger("click");
  await flushPromises();
};

beforeEach(() => {
  vi.clearAllMocks();
  API.resetSettings.mockResolvedValue({ data: structuredClone(RESET) });
});

afterEach(() => {
  for (const wrapper of wrappers.splice(0)) {
    wrapper.unmount();
  }
});

test("clearing a search from the series root it redirected into goes to the top", async () => {
  // Searched from the Publishers top; the search sent us to /series.
  setRoute("series");
  const { wrapper, store } = mountEmpty("batman");

  await clickClear(wrapper);

  expect(store.settings.search).toBe("");
  expect(store.settings.filters.bookmark).toBe("");
  expect(router.push).toHaveBeenCalledExactlyOnceWith({
    name: "browser",
    params: { collection: "publishers" },
  });
  // The route change reloads the page; nothing loads the stranded root.
  expect(API.getBrowserPage).not.toHaveBeenCalled();
});

test("clearing a search inside a series stays put and reloads", async () => {
  // Navigated into a series during the search: it has breadcrumbs.
  setRoute("series", "5");
  const { wrapper, store } = mountEmpty("batman");

  await clickClear(wrapper);

  expect(store.settings.search).toBe("");
  expect(router.push).not.toHaveBeenCalled();
  expect(API.getBrowserPage).toHaveBeenCalledOnce();
});

test("clearing only filters at the top stays put and reloads", async () => {
  setRoute("publishers");
  const { wrapper } = mountEmpty("");

  await clickClear(wrapper);

  expect(router.push).not.toHaveBeenCalled();
  expect(API.getBrowserPage).toHaveBeenCalledOnce();
});

export default {};
