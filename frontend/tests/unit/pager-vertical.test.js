/*
 * Tests for ``pager-vertical.vue`` page-to-index mapping.
 *
 * The vertical pager feeds ``v-virtual-scroll`` a list of page numbers, and
 * reverses that list for bottom-to-top reading. ``scrollToIndex`` takes an
 * index into that list, so a page number is only its own index while
 * reading top-to-bottom. Passing the page number straight through sent
 * bottom-to-top readers to the mirrored page — opening at page 0 landed on
 * the last page.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, test, vi } from "vitest";

import PagerVertical from "@/components/reader/pager/pager-vertical.vue";
import vuetify from "@/plugins/vuetify";

const PK = 7;
const MAX_PAGE = 9;
const PAST_THE_THROTTLE_WINDOW_MS = 1000;

let wrappers = [];

function mountPager(readingDirection) {
  const scrollToIndex = vi.fn();
  const pinia = createTestingPinia({
    // getBookSettings has to really run to return the seeded settings.
    stubActions: false,
    initialState: {
      reader: {
        page: 0,
        // Seeded settings are returned as-is by getBookSettings.
        bookSettings: {
          [PK]: {
            readingDirection,
            isVertical: true,
            isReadInReverse: readingDirection === "btt",
          },
        },
      },
    },
  });
  const wrapper = mount(PagerVertical, {
    props: { book: { pk: PK, maxPage: MAX_PAGE } },
    global: {
      plugins: [pinia, vuetify],
      stubs: {
        ScaleForScroll: { template: "<div><slot /></div>" },
        // The pager reaches the scroller through the ref, so the spy has
        // to live on the stub the ref resolves to.
        VVirtualScroll: { template: "<div />", methods: { scrollToIndex } },
      },
    },
  });
  wrappers.push(wrapper);
  return { wrapper, scrollToIndex };
}

afterEach(() => {
  for (const wrapper of wrappers) {
    wrapper.unmount();
  }
  wrappers = [];
});

describe("PagerVertical — scrolling to a page", () => {
  test("top to bottom scrolls to the page's own index", () => {
    const { wrapper, scrollToIndex } = mountPager("ttb");

    wrapper.vm.scrollToPage(3);

    expect(wrapper.vm.items[3]).toBe(3);
    expect(scrollToIndex).toHaveBeenCalledWith(3);
  });

  test("bottom to top scrolls to the page's mirrored index", () => {
    const { wrapper, scrollToIndex } = mountPager("btt");

    wrapper.vm.scrollToPage(3);

    expect(wrapper.vm.items[6]).toBe(3);
    expect(scrollToIndex).toHaveBeenCalledWith(6);
  });

  test("bottom to top opens page 0 at the end of the list", () => {
    const { wrapper, scrollToIndex } = mountPager("btt");

    wrapper.vm.scrollToPage(0);

    expect(scrollToIndex).toHaveBeenCalledWith(MAX_PAGE);
  });

  test("bottom to top reaches the last page at the top of the list", () => {
    const { wrapper, scrollToIndex } = mountPager("btt");

    wrapper.vm.scrollToPage(MAX_PAGE);

    expect(scrollToIndex).toHaveBeenCalledWith(0);
  });
});

/*
 * The scroll handler is throttled, and the trailing call is the one that
 * matters: a fling that ends inside a throttle window would otherwise never
 * read the final ``scrollTop``, so the book-change boundary check missed the
 * very scroll that reached the end of the book. VueUse v15 made trailing the
 * default; the component passes it explicitly so a future flip can't take it
 * away again.
 */
describe("PagerVertical scroll throttling", () => {
  test("runs on the leading edge and once more at the end of the window", async () => {
    vi.useFakeTimers();
    try {
      const { wrapper } = mountPager("ttb");
      const impl = vi
        .spyOn(wrapper.vm, "_scrollImpl")
        .mockImplementation(() => {});
      // Rebuild the throttled wrapper around the spy.
      wrapper.vm.$options.created.call(wrapper.vm);

      wrapper.vm.onScroll();
      wrapper.vm.onScroll();
      wrapper.vm.onScroll();
      expect(impl).toHaveBeenCalledTimes(1);

      // Well past the component's window, so the assertion is about the
      // trailing call existing at all rather than about its exact timing.
      await vi.advanceTimersByTimeAsync(PAST_THE_THROTTLE_WINDOW_MS);

      expect(impl).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
