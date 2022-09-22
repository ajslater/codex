import { createTestingPinia } from "@pinia/testing";
import { createLocalVue, mount } from "@vue/test-utils";
import { defineStore, PiniaVuePlugin } from "pinia";
import { expect, test, vi } from "vitest";
import VueRouter from "vue-router";
import Vuetify from "vuetify";

import ReaderNavButton from "@/components/reader/reader-nav-button.vue";

const BTN_DISABLED = "v-btn--disabled";

const setupVue = function (vue) {
  vue.use(VueRouter);
  vue.use(Vuetify);
  vue.use(PiniaVuePlugin);
};

const setupStore = function () {
  return defineStore("mockReader", {
    state: () => {
      return {
        routes: {
          current: {
            pk: 2,
            page: 5,
          },
        },
      };
    },
    actions: {
      setPage(state, pn) {
        state.routes.current.page = pn;
      },
      routeChanged({ commit }, pn) {
        commit("setPage", pn);
      },
    },
  });
};

const setupRouter = function () {
  return new VueRouter({
    routes: [
      { path: "/c/:pk/:page", name: "reader", component: ReaderNavButton },
    ],
  });
};

test("reader-nav-button", async () => {
  console.log("started test");
  expect(ReaderNavButton).toBeTruthy();

  const localVue = createLocalVue();
  setupVue(localVue);

  const store = setupStore();
  const router = setupRouter();
  const wrapper = mount(ReaderNavButton, {
    store,
    router,
    localVue,
    propsData: {
      value: 0,
    },
    stubs: ["router-link", "router-view"],
    global: {
      plugins: [createTestingPinia({ createSpy: vi.fn })],
    },
  });

  expect(wrapper.text()).toContain("0");
  expect(wrapper.html()).toMatchSnapshot();
  const btn = wrapper.findComponent({ name: "v-btn" });
  expect(btn.classes(BTN_DISABLED)).toBe(false);
  await wrapper.vm.$router.push({
    name: "reader",
    params: { pk: 2, page: 10 },
  });

  expect(btn.classes(BTN_DISABLED)).toBe(false);
  // doesn't work
  // await btn.trigger("click");
  wrapper.vm.$router.push({ name: "reader", params: { pk: 2, page: 0 } });
  await wrapper.vm.$nextTick();

  expect(btn.classes(BTN_DISABLED)).toBe(true);

  expect(wrapper.text()).toContain("0");
}, 1000);

export default {};
