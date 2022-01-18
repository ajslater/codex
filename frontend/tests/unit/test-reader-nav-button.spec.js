import { mount } from "@vue/test-utils";
import Vue from "vue";
import VueRouter from "vue-router";
import Vuetify from "vuetify";
import Vuex from "vuex";

// Can't figure out how to use @ refs in jest yet.
// eslint-disable-next-line import/no-unresolved
import ReaderNavButton from "../../src/components/reader-nav-button";

const setupVue = () => {
  Vue.use(VueRouter);
  Vue.use(Vuetify);
  Vue.use(Vuex);
};

const setupStore = () => {
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

  // eslint-disable-next-line import/no-named-as-default-member
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

const setupWrapper = () => {
  setupVue();
  const store = setupStore();
  const router = setupRouter();
  return mount(ReaderNavButton, {
    store,
    router,
    Vue,
    propsData: { value: 30 },
    stubs: ["router-link", "router-view"],
  });
};

describe("readerNavButton.vue", () => {
  it("test enable disable with vuex change", async () => {
    // setup
    expect.assertions(4);
    const wrapper = setupWrapper();

    expect(wrapper.vm.value).toBe(30);
    wrapper.vm.$router.push({ name: "reader", params: { pk: 2, page: 10 } });

    let btn = wrapper.findComponent({ name: "v-btn" });
    expect(btn.exists()).toBe(true);
    expect(btn.classes("v-btn--disabled")).toBe(false);

    // Would be nice to get this to work. Might require createLocalVue?
    // btn.trigger("click");
    wrapper.vm.$router.push({ name: "reader", params: { pk: 2, page: 30 } });
    await wrapper.vm.$nextTick();
    expect(btn.classes("v-btn--disabled")).toBe(true);
  });
});
