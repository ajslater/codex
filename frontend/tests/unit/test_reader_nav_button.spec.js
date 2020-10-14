import { createLocalVue, mount } from "@vue/test-utils";
import Vue from "vue";
import VueRouter from "vue-router";
import Vuetify from "vuetify";
import Vuex from "vuex";

import ReaderNavButton from "../../src/components/reader-nav-button";

// Global Vuetify prevents warning message: https://github.com/vuetifyjs/vuetify/discussions/4068#issuecomment-422406319
Vue.use(Vuetify);

Vue.use(VueRouter);

describe("ReaderNavButton.vue", () => {
  const state = {
    routes: {
      current: {
        pk: 2,
        page: 10,
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

  let wrapper;
  let store;
  let router;

  beforeEach(() => {
    const localVue = createLocalVue();

    localVue.use(Vuex);
    localVue.use(Vuetify);
    localVue.use(VueRouter);

    store = new Vuex.Store({
      modules: {
        reader: {
          namespaced: true,
          state,
          mutations,
          actions,
        },
      },
    });

    router = new VueRouter({
      routes: [
        { path: "/c/:pk/:page", name: "reader", component: ReaderNavButton },
      ],
    });

    wrapper = mount(ReaderNavButton, {
      store,
      router,
      localVue,
      propsData: { value: 30 },
      stubs: ["router-link", "router-view"],
    });
  });

  it("test enable disable with vuex change", async () => {
    expect(wrapper.vm.value).toBe(30);
    wrapper.vm.$router.push({ name: "reader", params: { pk: 2, page: 10 } });

    let btn = wrapper.findComponent({ name: "v-btn" });
    expect(btn.exists()).toBe(true);
    expect(btn.classes("v-btn--disabled")).toBe(false);

    return wrapper.vm.$router
      .push({ name: "reader", params: { pk: 2, page: 30 } })
      .then(() => {
        expect(btn.classes("v-btn--disabled")).toBe(true);
      });
  });
});
