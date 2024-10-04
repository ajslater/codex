/* Simple test just to play with vitest. */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { expect, test } from "vitest";
import { createRouter, createWebHistory } from "vue-router";

// This breaks eslint-plugin-import, could be solved with import assertions
// https://stackoverflow.com/questions/71090960/is-there-a-way-to-make-eslint-understand-the-new-import-assertion-syntax-without
// eslint-disable-next-line
import ReaderNavButton from "@/components/reader/toolbars/nav/reader-nav-button.vue";
import vuetify from "@/plugins/vuetify";
import { useReaderStore } from "@/stores/reader";

const BTN_DISABLED = "v-btn--disabled";

const setupRouter = function () {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: "/c/:pk/:page", name: "reader", component: ReaderNavButton },
    ],
  });
};

test("reader-nav-button", async () => {
  console.info("started test");
  expect(ReaderNavButton).toBeTruthy();

  const router = setupRouter();
  router.push("/c/2/0");
  await router.isReady();
  const store = createTestingPinia({
    initialState: { reader: { books: { current: { pk: 0 } }, page: 0 } },
  });
  const wrapper = mount(ReaderNavButton, {
    props: {
      value: 0,
      twoPages: false,
    },
    global: {
      plugins: [router, vuetify, store],
      stubs: ["router-link", "router-view"],
    },
  });
  const readerStore = useReaderStore();

  // test initial state
  expect(wrapper.html()).toMatchSnapshot();
  expect(wrapper.text()).toContain("0");

  // push new route
  const btn = wrapper.findComponent({ name: "v-btn" });

  expect(btn.classes(BTN_DISABLED)).toBe(true);
  await wrapper.vm.$router.push({
    params: { pk: 2, page: 10 },
  });
  readerStore.page = 10;
  await wrapper.vm.$nextTick();
  expect(btn.classes(BTN_DISABLED)).toBe(false);

  // push back to original state
  await wrapper.vm.$router.push({ params: { pk: 2, page: 0 } });
  readerStore.page = 0;
  await wrapper.vm.$nextTick();
  expect(btn.classes(BTN_DISABLED)).toBe(true);

  expect(wrapper.text()).toContain("0");
}, 1000);

export default {};
