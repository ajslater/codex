import { mount } from "@vue/test-utils";
import { expect, test } from "vitest";
import { createRouter, createWebHistory } from "vue-router";

import ReaderNavButton from "@/components/reader/reader-nav-button.vue";
import vuetify from "@/plugins/vuetify";

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
  console.log("started test");
  expect(ReaderNavButton).toBeTruthy();

  const router = setupRouter();
  router.push("/c/2/0");
  await router.isReady();
  const wrapper = mount(ReaderNavButton, {
    props: {
      value: 0,
      twoPages: false,
    },
    global: {
      plugins: [router, vuetify],
      stubs: ["router-link", "router-view"],
    },
  });

  // test initial state
  expect(wrapper.html()).toMatchSnapshot();
  expect(wrapper.text()).toContain("0");

  // push new route
  const btn = wrapper.findComponent({ name: "v-btn" });
  expect(btn.classes(BTN_DISABLED)).toBe(true);
  await wrapper.vm.$router.push({
    params: { pk: 2, page: 10 },
  });
  // await router.isReady();
  await wrapper.vm.$nextTick();
  expect(btn.classes(BTN_DISABLED)).toBe(false);

  // push back to original state
  await wrapper.vm.$router.push({ params: { pk: 2, page: 0 } });
  // await router.isReady();
  await wrapper.vm.$nextTick();
  expect(btn.classes(BTN_DISABLED)).toBe(true);

  expect(wrapper.text()).toContain("0");
}, 1000);

export default {};
