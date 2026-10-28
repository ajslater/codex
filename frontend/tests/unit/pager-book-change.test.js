/*
 * Tests for when ``pager.vue`` sets the active page.
 *
 * ``setActivePage`` pages and bookmarks the store's current book. On a book
 * change the route moves to the new book before ``loadBooks`` swaps the
 * books, and the book-change flag has already mounted the new book's pager.
 * That pager used to answer the route at once, so the book being left got
 * the new book's page: a keyboard change from the end of a book reset that
 * book's bookmark to page 0.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, test } from "vitest";
import { createRouter, createWebHistory } from "vue-router";

import Pager from "@/components/reader/pager/pager.vue";
import vuetify from "@/plugins/vuetify";
import { useReaderStore } from "@/stores/reader";

const LEAVING = Object.freeze({ pk: 3, maxPage: 19 });
const NEXT = Object.freeze({ pk: 4, maxPage: 9 });

const wrappers = [];

async function mountPager(book) {
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: "/read/:pk", name: "reader", component: Pager }],
  });
  router.push(`/read/${LEAVING.pk}?page=${LEAVING.maxPage}`);
  await router.isReady();
  const pinia = createTestingPinia({
    stubActions: true,
    initialState: {
      reader: {
        books: { current: LEAVING, prev: false, next: NEXT },
        page: LEAVING.maxPage,
      },
    },
  });
  const store = useReaderStore(pinia);
  store.getBookSettings.mockReturnValue({});
  const wrapper = mount(Pager, {
    props: { book },
    global: {
      plugins: [router, vuetify, pinia],
      stubs: { PagerHorizontal: true, PagerVertical: true },
    },
  });
  wrappers.push(wrapper);
  return { router, store, wrapper };
}

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers.length = 0;
});

describe("Pager — setting the active page", () => {
  test("the current book's pager follows its route", async () => {
    const { router, store } = await mountPager(LEAVING);

    expect(store.setActivePage).toHaveBeenCalledExactlyOnceWith(
      LEAVING.maxPage,
      true,
    );

    await router.push(`/read/${LEAVING.pk}?page=5`);

    expect(store.setActivePage).toHaveBeenLastCalledWith(5, true);
  });

  test("the next book's pager waits until its book is current", async () => {
    const { router, store, wrapper } = await mountPager(NEXT);

    await router.push(`/read/${NEXT.pk}?page=0`);

    expect(store.setActivePage).not.toHaveBeenCalled();

    store.books.current = NEXT;
    await wrapper.vm.$nextTick();

    expect(store.setActivePage).toHaveBeenCalledExactlyOnceWith(0, true);
  });
});
