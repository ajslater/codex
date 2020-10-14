import { createLocalVue, mount } from "@vue/test-utils";
import Vue from "vue";
import Vuetify from "vuetify";
import Vuex from "vuex";

import ReaderNavButton from "../../src/components/reader-nav-button";

// Global Vuetify prevents warning message: https://github.com/vuetifyjs/vuetify/discussions/4068#issuecomment-422406319
Vue.use(Vuetify);

describe("ReaderNavButton.vue", () => {
  const state = {
    routes: {
      current: {
        pk: 2,
        pageNumber: 10,
      },
    },
  };
  const mutations = {
    setPage(state, pn) {
      state.routes.current.pageNumber = pn;
    },
  };
  const actions = {
    routeChanged({ commit }, pn) {
      commit("setPage", pn);
    },
  };
  let wrapper;
  let store;

  beforeEach(() => {
    const localVue = createLocalVue();

    localVue.use(Vuex);
    localVue.use(Vuetify);

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

    wrapper = mount(ReaderNavButton, {
      store,
      localVue,
      propsData: { value: 30 },
      stubs: ["router-link", "router-view"],
    });
  });

  it("test enable disable with vuex change", async () => {
    expect(wrapper.vm.value).toBe(30);

    let btn = wrapper.findComponent({ name: "v-btn" });
    expect(btn.exists()).toBe(true);
    expect(btn.classes("v-btn--disabled")).toBe(false);

    return store.dispatch("reader/routeChanged", 30).then(() => {
      /*
      console.log(store.state.reader);
      console.log(btn.classes());
      console.log(wrapper.vm.disabled);
      */
      expect(btn.classes("v-btn--disabled")).toBe(true);
    });
  });
});
