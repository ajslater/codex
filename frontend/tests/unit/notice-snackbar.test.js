import { mount } from "@vue/test-utils";
/*
 * App-wide notices: the common store's ``setNotice`` / ``setErrorNotice``
 * and ``notice-snackbar.vue``, which shows them. Reading list actions
 * report here because they happen outside forms, where ``form.success``
 * and ``form.errors`` have nothing to show them.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, test } from "vitest";

import NoticeSnackbar from "@/components/notice-snackbar.vue";
import vuetify from "@/plugins/vuetify";
import { useCommonStore } from "@/stores/common";

// Render the snackbar body inline instead of through Vuetify's overlay.
const VSnackbarStub = {
  name: "VSnackbar",
  props: ["modelValue", "color", "timeout"],
  emits: ["update:modelValue"],
  template:
    "<div v-if='modelValue' id='snackbar' :data-color='color' :data-timeout='timeout'><slot /><slot name='actions' /></div>",
};

const mountSnackbar = (pinia) =>
  mount(NoticeSnackbar, {
    global: { plugins: [vuetify, pinia], stubs: { VSnackbar: VSnackbarStub } },
  });

describe("notices", () => {
  let pinia;
  beforeEach(() => {
    pinia = createPinia();
    setActivePinia(pinia);
  });

  test("a notice shows, and Dismiss clears it", async () => {
    const wrapper = mountSnackbar(pinia);
    expect(wrapper.find("#snackbar").exists()).toBe(false);
    const store = useCommonStore();
    store.setNotice('Copied to your reading lists as "Civil War (copy)".');
    await wrapper.vm.$nextTick();
    const snackbar = wrapper.find("#snackbar");
    expect(snackbar.text()).toContain("Civil War (copy)");
    expect(snackbar.attributes("data-color")).toBeUndefined();
    await wrapper.find("button").trigger("click");
    expect(store.notice.text).toBe("");
    expect(wrapper.find("#snackbar").exists()).toBe(false);
  });

  test("an error notice reads the server's message and stays longer", async () => {
    const wrapper = mountSnackbar(pinia);
    useCommonStore().setErrorNotice({
      response: { status: 404, data: { detail: "No such reading list." } },
    });
    await wrapper.vm.$nextTick();
    const snackbar = wrapper.find("#snackbar");
    expect(snackbar.text()).toContain("No such reading list.");
    expect(snackbar.attributes("data-color")).toBe("error");
    expect(Number(snackbar.attributes("data-timeout"))).toBeGreaterThan(4000);
  });

  test("a notice leaves the form's messages alone", () => {
    const store = useCommonStore();
    store.setSuccess("Saved.");
    store.setNotice("Added 1 comic to My Spidey.");
    expect(store.form.success).toBe("Saved.");
  });
});
