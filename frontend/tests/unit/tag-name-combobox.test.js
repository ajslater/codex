/*
 * TagNameCombobox: the tag editor's suggesting combobox.
 *
 * Nothing loads until the menu opens. Typing with the menu open asks again,
 * debounced; Vuetify's other update:search emits (model assignment, a pick,
 * a chip add) happen with the menu closed or settle back to the cached "",
 * so a closed menu never fetches. Everything the panel set on a plain
 * v-combobox still reaches the inner one.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";

import TagNameCombobox from "@/components/metadata/edit-mode/tag-name-combobox.vue";
import vuetify from "@/plugins/vuetify";
import { useMetadataStore } from "@/stores/metadata";

const DEBOUNCE_MS = 250;

function mountCombobox({
  props = {},
  slots = {},
  tagNames = {},
  attachTo,
} = {}) {
  const pinia = createTestingPinia({
    initialState: { metadata: { md: {}, tagNames, tagNamesLoading: {} } },
  });
  const wrapper = mount(TagNameCombobox, {
    props: { field: "genres", ...props },
    slots,
    attachTo,
    global: { plugins: [pinia, vuetify] },
  });
  const inner = wrapper.findComponent({ name: "VCombobox" });
  return { wrapper, inner, store: useMetadataStore() };
}

describe("TagNameCombobox", () => {
  beforeAll(() => {
    // VOverlay reads the bare global; happy-dom has no visual viewport.
    globalThis.visualViewport ??= {
      width: 1024,
      height: 768,
      offsetLeft: 0,
      offsetTop: 0,
      scale: 1,
      addEventListener() {},
      removeEventListener() {},
    };
  });

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.replaceChildren();
  });

  test("opening the menu loads every name", async () => {
    const { inner, store } = mountCombobox({
      props: { field: "imprint", scope: { publisher: "DC Comics" } },
    });
    expect(store.loadTagNames).not.toHaveBeenCalled();

    inner.vm.$emit("update:menu", true);
    await flushPromises();

    expect(store.loadTagNames).toHaveBeenCalledExactlyOnceWith({
      field: "imprint",
      scope: { publisher: "DC Comics" },
      q: "",
    });
  });

  test("typing with the menu open debounces to one request", async () => {
    const { inner, store } = mountCombobox({
      props: { field: "characters", scope: {} },
    });
    inner.vm.$emit("update:menu", true);
    store.loadTagNames.mockClear();

    inner.vm.$emit("update:search", "B");
    inner.vm.$emit("update:search", "Ba");
    inner.vm.$emit("update:search", "Bat");
    vi.advanceTimersByTime(DEBOUNCE_MS - 1);
    expect(store.loadTagNames).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(store.loadTagNames).toHaveBeenCalledExactlyOnceWith({
      field: "characters",
      scope: {},
      q: "Bat",
    });
  });

  test("real typing opens the menu before it searches", async () => {
    // The gate must not swallow real input: Vuetify opens the menu on the
    // first keystroke, before it emits update:search.
    const { wrapper, store } = mountCombobox({
      props: { field: "characters" },
      attachTo: document.body,
    });
    const input = wrapper.find("input");
    await input.trigger("focus");
    await input.setValue("Bat");
    await flushPromises();
    expect(store.loadTagNames).toHaveBeenCalledWith({
      field: "characters",
      scope: {},
      q: "",
    });

    vi.advanceTimersByTime(DEBOUNCE_MS);
    expect(store.loadTagNames).toHaveBeenLastCalledWith({
      field: "characters",
      scope: {},
      q: "Bat",
    });
    wrapper.unmount();
  });

  test("a search with the menu closed never loads", async () => {
    const { inner, store } = mountCombobox();
    // initFromMetadata assigning the model emits this.
    inner.vm.$emit("update:search", "Horror");
    vi.advanceTimersByTime(DEBOUNCE_MS * 2);
    expect(store.loadTagNames).not.toHaveBeenCalled();
  });

  test("a menu closing before the debounce fires cancels the load", async () => {
    const { inner, store } = mountCombobox();
    inner.vm.$emit("update:menu", true);
    store.loadTagNames.mockClear();

    // A pick sets the search to the picked title, then closes the menu.
    inner.vm.$emit("update:search", "Horror");
    inner.vm.$emit("update:menu", false);
    vi.advanceTimersByTime(DEBOUNCE_MS * 2);
    expect(store.loadTagNames).not.toHaveBeenCalled();
  });

  test("the group's own values come first and duplicates drop", async () => {
    const { inner } = mountCombobox({
      props: { field: "volume", extraItems: [2014, "2000"] },
      tagNames: {
        volume: { "[]": { "": { names: [1989, 2014, 2000], complete: true } } },
      },
    });
    await flushPromises();
    expect(inner.props("items")).toStrictEqual([2014, "2000", 1989]);
  });

  test("the menu can open on an empty list and shows why", async () => {
    const { inner, store } = mountCombobox();
    expect(inner.props("hideNoData")).toBe(false);
    expect(inner.props("filteredOrder")).toBe("prefix");
    expect(inner.props("noDataText")).toBe("No matches — Enter adds it");

    store.tagNamesLoading = { genres: true };
    await flushPromises();
    expect(inner.props("loading")).toBe(true);
    expect(inner.props("noDataText")).toBe("Loading…");
  });

  test("a single string v-model round-trips", async () => {
    const onUpdate = vi.fn();
    const { inner } = mountCombobox({
      props: {
        field: "publisher",
        modelValue: "DC Comics",
        "onUpdate:modelValue": onUpdate,
        label: "Publisher",
      },
    });
    expect(inner.props("modelValue")).toBe("DC Comics");
    expect(inner.props("label")).toBe("Publisher");

    inner.vm.$emit("update:modelValue", "Marvel");
    expect(onUpdate).toHaveBeenCalledWith("Marvel");
  });

  test("a string array v-model round-trips", async () => {
    const onUpdate = vi.fn();
    const { inner } = mountCombobox({
      props: {
        modelValue: ["Horror"],
        "onUpdate:modelValue": onUpdate,
        multiple: true,
        chips: true,
      },
    });
    expect(inner.props("modelValue")).toStrictEqual(["Horror"]);
    expect(inner.props("multiple")).toBe(true);

    inner.vm.$emit("update:modelValue", ["Horror", "Noir"]);
    expect(onUpdate).toHaveBeenCalledWith(["Horror", "Noir"]);
  });

  test("the append-inner slot renders", async () => {
    const { wrapper } = mountCombobox({
      slots: { "append-inner": '<span class="clearProbe">x</span>' },
    });
    await flushPromises();
    expect(wrapper.find(".clearProbe").exists()).toBe(true);
  });
});
