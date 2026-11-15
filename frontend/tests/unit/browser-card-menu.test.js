/*
 * Unit tests for ``browser-card-menu.vue`` — the cover card's action
 * menu. Covers its Shelves entry: a submenu for a single-id card, and
 * absent for a card that aggregates several ids, which can't be
 * shelved atomically. The other entries are stubbed; they have their
 * own components and tests.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, test } from "vitest";

import BrowserCardMenu from "@/components/browser/card/browser-card-menu.vue";
import ShelfMenu from "@/components/shelf-menu.vue";
import vuetify from "@/plugins/vuetify";

beforeAll(() => {
  // VOverlay's connected location strategy reads the bare global.
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

const STUBS = Object.freeze({
  DownloadButton: true,
  ForceUpdateButton: true,
  MarkReadButton: true,
  RemoveCoverButton: true,
  UploadCoverButton: true,
});

const wrappers = [];

async function mountOpenMenu(item) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { pk: 1 } },
      shelves: { shelves: [], hydrated: true },
    },
    stubActions: true,
  });
  const wrapper = mount(BrowserCardMenu, {
    attachTo: document.body,
    global: { plugins: [pinia, vuetify], stubs: STUBS },
    props: { item },
  });
  wrappers.push(wrapper);
  wrapper.vm.showMenu = true;
  await flushPromises();
  return wrapper;
}

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
});

describe("BrowserCardMenu — Shelves", () => {
  test("a single-id card gets a Shelves submenu", async () => {
    const wrapper = await mountOpenMenu({ collection: "series", ids: [7] });
    const shelfMenu = wrapper.findComponent(ShelfMenu);
    expect(shelfMenu.props()).toMatchObject({
      collection: "series",
      pk: 7,
      location: "end",
    });
    const entry = document.querySelector(".shelvesListItem");
    expect(entry.textContent).toContain("Shelves");
  });

  test("a card aggregating several ids gets no Shelves entry", async () => {
    const wrapper = await mountOpenMenu({ collection: "folders", ids: [3, 4] });
    expect(wrapper.findComponent(ShelfMenu).exists()).toBe(false);
    expect(document.querySelector(".shelvesListItem")).toBeNull();
  });
});
