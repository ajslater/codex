/*
 * Tests for the browser card menu's admin cover controls,
 * ``upload-cover-button.vue`` and ``remove-cover-button.vue``.
 *
 * Both load the admin API client with a dynamic ``import()`` inside their
 * handlers so it stays out of the browser bundle. These tests pin down that
 * the lazy load still reaches the API with the card's collection and ids,
 * busts the card's cover, and reports a failure; and that neither control
 * renders for a non-admin.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { removeCustomCover, uploadCustomCover } from "@/api/v4/admin";
import RemoveCoverButton from "@/components/browser/card/remove-cover-button.vue";
import UploadCoverButton from "@/components/browser/card/upload-cover-button.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

vi.mock(import("@/api/v4/admin"), async (importOriginal) => ({
  ...(await importOriginal()),
  removeCustomCover: vi.fn(),
  uploadCustomCover: vi.fn(),
}));

const ADMIN = Object.freeze({ pk: 1, isStaff: true });
const USER = Object.freeze({ pk: 2, isStaff: false });

function mountButton(component, item, user = ADMIN) {
  const pinia = createTestingPinia({
    stubActions: true,
    initialState: { auth: { user } },
  });
  const wrapper = mount(component, {
    global: { plugins: [pinia, vuetify] },
    props: { item },
  });
  return {
    wrapper,
    browserStore: useBrowserStore(),
    commonStore: useCommonStore(),
  };
}

async function pickFile(wrapper, file) {
  const input = wrapper.find("input[type=file]");
  Object.defineProperty(input.element, "files", { value: [file] });
  await input.trigger("change");
  await settle();
}

function seriesItem(overrides = {}) {
  return { collection: "series", ids: [4, 9], pk: 4, ...overrides };
}

async function settle() {
  await vi.dynamicImportSettled();
  await flushPromises();
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("UploadCoverButton", () => {
  test("uploads the picked file and busts the card cover", async () => {
    uploadCustomCover.mockResolvedValue({ data: { customCoverPk: 42 } });
    const item = seriesItem();
    const { wrapper, browserStore } = mountButton(UploadCoverButton, item);
    const file = new File(["png"], "cover.png", { type: "image/png" });

    await pickFile(wrapper, file);

    expect(uploadCustomCover).toHaveBeenCalledExactlyOnceWith({
      collection: "series",
      pks: [4, 9],
      file,
    });
    expect(browserStore.bustCoverCache).toHaveBeenCalledExactlyOnceWith({
      ids: [4, 9],
      coverCustomPk: 42,
    });
    expect(wrapper.emitted("uploaded")).toStrictEqual([[42]]);
  });

  test("a rejected upload shows the server's reason", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    uploadCustomCover.mockRejectedValue({
      response: { data: { detail: "Not an image." } },
    });
    const { wrapper, browserStore, commonStore } = mountButton(
      UploadCoverButton,
      seriesItem(),
    );

    await pickFile(wrapper, new File(["x"], "x.txt"));

    expect(commonStore.setSessionError).toHaveBeenCalledExactlyOnceWith(
      "Not an image.",
    );
    expect(browserStore.bustCoverCache).not.toHaveBeenCalled();
    expect(wrapper.emitted("uploaded")).toBeUndefined();
  });

  test("renders nothing for a non-admin", () => {
    const { wrapper } = mountButton(UploadCoverButton, seriesItem(), USER);
    expect(wrapper.find("input[type=file]").exists()).toBe(false);
  });
});

describe("RemoveCoverButton", () => {
  test("confirming removes the cover and busts the card cover", async () => {
    removeCustomCover.mockResolvedValue({});
    const item = seriesItem({ coverCustomPk: 42 });
    const { wrapper, browserStore } = mountButton(RemoveCoverButton, item);

    wrapper.findComponent(ConfirmDialog).vm.$emit("confirm");
    await settle();

    expect(removeCustomCover).toHaveBeenCalledExactlyOnceWith({
      collection: "series",
      pks: [4, 9],
    });
    expect(browserStore.bustCoverCache).toHaveBeenCalledExactlyOnceWith({
      ids: [4, 9],
      coverCustomPk: null,
    });
    expect(wrapper.emitted("removed")).toHaveLength(1);
  });

  test("renders nothing for a non-admin", () => {
    const item = seriesItem({ coverCustomPk: 42 });
    const { wrapper } = mountButton(RemoveCoverButton, item, USER);
    expect(wrapper.findComponent(ConfirmDialog).exists()).toBe(false);
  });
});
