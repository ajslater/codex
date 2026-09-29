/*
 * Deleting saved browser views: the store action and the trash icon
 * on each saved view in the settings drawer's "Load Saved View" menu.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";

vi.mock("@/plugins/router", () => ({
  default: { currentRoute: { value: { params: {}, query: {} } } },
}));
vi.mock("@/api/v4/browser", () => ({
  deleteSavedSettings: vi.fn(),
  getSavedSettingsList: vi.fn(),
}));

import * as API from "@/api/v4/browser";
import BrowserSettingsSaved from "@/components/browser/drawer/browser-settings-saved.vue";
import vuetify from "@/plugins/vuetify";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

const SAVED = [
  { pk: 3, name: "Added Recently" },
  { pk: 7, name: "DC by Year" },
];

beforeEach(() => {
  API.deleteSavedSettings.mockReset().mockResolvedValue({});
  API.getSavedSettingsList
    .mockReset()
    .mockResolvedValue({ data: { savedSettings: [SAVED[0]] } });
});

const makeStore = (isLoggedIn = true) => {
  setActivePinia(createPinia());
  useAuthStore().user = isLoggedIn ? { pk: 1 } : null;
  return useBrowserStore();
};

const deleteButtons = () => [
  ...document.querySelectorAll(".savedSettingsDeleteBtn"),
];

describe("deleteSavedSettings store action", () => {
  test("deletes by pk, then reloads the list", async () => {
    const store = makeStore();
    store.savedSettingsList = SAVED;

    await store.deleteSavedSettings(7);
    await flushPromises();

    expect(API.deleteSavedSettings).toHaveBeenCalledWith(7);
    expect(store.savedSettingsList).toStrictEqual([SAVED[0]]);
  });

  test("still reloads when the delete fails", async () => {
    const store = makeStore();
    vi.spyOn(console, "error").mockImplementation(() => {});
    API.deleteSavedSettings.mockRejectedValue(new Error("404"));

    await store.deleteSavedSettings(7);
    await flushPromises();

    expect(API.getSavedSettingsList).toHaveBeenCalled();
  });

  test("does nothing when unauthorized", async () => {
    const store = makeStore(false);

    await store.deleteSavedSettings(7);

    expect(API.deleteSavedSettings).not.toHaveBeenCalled();
    expect(API.getSavedSettingsList).not.toHaveBeenCalled();
  });
});

describe("saved view trash icon", () => {
  let wrapper;

  beforeAll(() => {
    // VOverlay reads the bare global; happy-dom has no visual viewport.
    globalThis.visualViewport ??= {
      width: 1024,
      height: 768,
      offsetLeft: 0,
      offsetTop: 0,
      scale: 1,
      addEventListener() {},
      removeEventListener() {},
    };
  });

  const mountSaved = async () => {
    const pinia = createTestingPinia({
      initialState: { browser: { savedSettingsList: SAVED } },
    });
    wrapper = mount(BrowserSettingsSaved, {
      attachTo: document.body,
      global: { plugins: [vuetify, pinia] },
    });
    // Open the combobox menu so its items render.
    await wrapper.find(".v-field").trigger("mousedown");
    await flushPromises();
    return useBrowserStore(pinia);
  };

  afterEach(() => {
    wrapper?.unmount();
    document.body.replaceChildren();
  });

  test("every saved view gets a trash icon", async () => {
    await mountSaved();

    expect(deleteButtons()).toHaveLength(SAVED.length);
  });

  test("the trash icon asks to confirm and doesn't load the view", async () => {
    const store = await mountSaved();

    deleteButtons()[1].click();
    await flushPromises();

    expect(document.body.textContent).toContain(
      'Delete the saved view "DC by Year"?',
    );
    expect(store.loadSavedSettings).not.toHaveBeenCalled();
    expect(store.deleteSavedSettings).not.toHaveBeenCalled();
  });

  test("confirming deletes that view", async () => {
    const store = await mountSaved();
    deleteButtons()[1].click();
    await flushPromises();

    const confirm = [...document.querySelectorAll("button")].find(
      (button) => button.textContent.trim() === "Delete",
    );
    confirm.click();
    await flushPromises();

    expect(store.deleteSavedSettings).toHaveBeenCalledWith(7);
  });
});

export default {};
