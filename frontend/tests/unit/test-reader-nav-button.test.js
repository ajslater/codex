import { createLocalVue, mount } from "@vue/test-utils";
import VueRouter from "vue-router";
import Vuetify from "vuetify";
import Vuex from "vuex";

import ReaderNavButton from "@/components/reader-nav-button.vue";

const { expect, test } = import.meta.vitest;

// XXX fix multiple vue instances https://github.com/vuetifyjs/vuetify/issues/4068
const localVue = createLocalVue();
const setupVue = () => {
  localVue.use(VueRouter);
  localVue.use(Vuetify);
  localVue.use(Vuex);
};

const setupStore = () => {
  const state = {
    routes: {
      current: {
        pk: 2,
        page: 5,
      },
    },
  };
  const mutations = {
    setPage(state, pn) {
      state.routes.current.page = pn;
    },
  };
  const actions = {
    routeChanged({ commit }, pn) {
      commit("setPage", pn);
    },
  };
  return new Vuex.Store({
    modules: {
      reader: {
        namespaced: true,
        state,
        mutations,
        actions,
      },
    },
  });
};

const setupRouter = () => {
  return new VueRouter({
    routes: [
      { path: "/c/:pk/:page", name: "reader", component: ReaderNavButton },
    ],
  });
};

const DISABLED_CLASS = "v-btn--disabled";

test("mount component", async () => {
  expect(ReaderNavButton).toBeTruthy();

  setupVue();
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
  });

  expect(wrapper.text()).toContain("0");
  expect(wrapper.html()).toMatchSnapshot();
  const btn = wrapper.findComponent({ name: "v-btn" });
  expect(btn.classes(DISABLED_CLASS)).toBe(false);

  await wrapper.vm.$router.push({
    name: "reader",
    params: { pk: 2, page: 10 },
  });
  expect(btn.classes(DISABLED_CLASS)).toBe(false);

  // doesn't work
  // await btn.trigger("click");
  wrapper.vm.$router.push({ name: "reader", params: { pk: 2, page: 0 } });
  await wrapper.vm.$nextTick();

  expect(btn.classes(DISABLED_CLASS)).toBe(true);

  expect(wrapper.text()).toContain("0");
});
