/*
 * Tests for ``book-change-drawer.vue`` — the prev/next book slide-outs.
 *
 * The drawer is 33vw, not Vuetify's 256px default. Vuetify 4.1 parked an
 * inactive layout item at ``translateX(-(width prop + 1)px)``, which left a
 * 33vw drawer partly on screen, so the width used to be applied only while
 * open (commit 24f8d1bd6). Vuetify 4.2 parks it at ``calc(±100% ± 1px)`` of
 * its own rendered box, so the width is now unconditional. These tests pin
 * the offscreen transform that makes that safe.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, test } from "vitest";

import { VApp } from "vuetify/components";

import BookChangeDrawer from "@/components/reader/book-change-drawer.vue";
import vuetify from "@/plugins/vuetify";

const MAX_PAGE = 10;

let wrappers = [];

async function mountDrawer(direction, { bookChange } = {}) {
  const pinia = createTestingPinia({
    // The drawer's location, icon and visibility all come from store actions.
    stubActions: false,
    initialState: {
      reader: {
        // Each drawer only shows at its own end of the book.
        page: direction === "prev" ? 0 : MAX_PAGE,
        bookChange,
        books: {
          current: { maxPage: MAX_PAGE },
          prev: { pk: 1 },
          next: { pk: 3 },
        },
        routes: {
          books: { prev: { pk: 1, page: 0 }, next: { pk: 3, page: 0 } },
        },
      },
    },
  });
  /*
   * vite-plugin-vuetify's autoImport only rewrites SFC templates, so a
   * runtime-compiled one has to register VApp itself. The drawer is a
   * layout item and throws without it.
   */
  const Host = {
    components: { BookChangeDrawer, VApp },
    props: { direction: { type: String, required: true } },
    template: `
      <VApp>
        <BookChangeDrawer :direction="direction" />
      </VApp>
    `,
  };
  const wrapper = mount(Host, {
    attachTo: document.body,
    props: { direction },
    global: { plugins: [pinia, vuetify], stubs: { RouterLink: true } },
  });
  wrappers.push(wrapper);
  await flushPromises();
  return wrapper.find(".v-navigation-drawer");
}

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers = [];
});

describe("BookChangeDrawer — offscreen when closed", () => {
  test("the previous-book drawer parks a full width to the left", async () => {
    const drawer = await mountDrawer("prev");

    expect(drawer.exists()).toBe(true);
    expect(drawer.attributes("style")).toContain(
      "translateX(calc(-100% + -1px))",
    );
  });

  test("the next-book drawer parks a full width to the right", async () => {
    const drawer = await mountDrawer("next");

    expect(drawer.attributes("style")).toContain(
      "translateX(calc(100% + 1px))",
    );
  });

  test("an open drawer is not translated", async () => {
    const drawer = await mountDrawer("prev", { bookChange: "prev" });

    expect(drawer.attributes("style")).toContain("translateX(0px)");
  });

  test("the width class is applied regardless of open state", async () => {
    const closed = await mountDrawer("prev");
    const open = await mountDrawer("prev", { bookChange: "prev" });

    for (const drawer of [closed, open]) {
      expect(drawer.classes()).toContain("bookChangeDrawer");
      expect(drawer.classes()).not.toContain("drawerActivated");
    }
  });
});
