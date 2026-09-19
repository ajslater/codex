/*
 * Tests for ``mark-read-button.vue`` — the "Mark Entire <Collection> Read"
 * control shared by the browser card kebab menu and the metadata panel.
 *
 * The confirm gate reads ``item.childCount``, which is the key browser card
 * items actually carry on the wire. It used to read ``item.children``, a key
 * only the metadata panel supplied, so "Mark Entire Publisher Read" from a
 * card marked every issue under the publisher with no confirmation at all.
 * Both callers now speak ``childCount``; these tests pin that down from both
 * entry points, and that a comic (no child key) still skips the dialog.
 *
 * ``v-dialog`` is stubbed so the overlay/teleport machinery happy-dom lacks
 * stays out of it; the stub keeps the activator slot and the open/closed
 * state so a click travels the same path it does in the app.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import MarkReadButton from "@/components/mark-read-button.vue";
import MetadataControls from "@/components/metadata/metadata-controls.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

const VDialogStub = Object.freeze({
  name: "VDialog",
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: `<div class="dialogStub">
    <slot name="activator" :props="{ onClick: () => $emit('update:modelValue', true) }" />
    <slot v-if="modelValue" />
  </div>`,
});

// A collection card as the browser API serializes it: ``childCount``, no
// ``children``.
function collectionItem(overrides = {}) {
  return {
    childCount: 12,
    collection: "publishers",
    finished: false,
    ids: [3],
    name: "Youthful",
    pk: 3,
    ...overrides,
  };
}

// A comic card: ``annotate_child_count`` early-returns for Comic, so cards
// for comics carry no child key at all.
function comicItem(overrides = {}) {
  return {
    collection: "comics",
    finished: false,
    ids: [7],
    name: "Captain Science #1",
    pk: 7,
    ...overrides,
  };
}

function mountButton(item) {
  const pinia = createTestingPinia({ stubActions: true });
  const wrapper = mount(MarkReadButton, {
    global: { plugins: [pinia, vuetify], stubs: { VDialog: VDialogStub } },
    props: { button: false, item },
  });
  return { wrapper, browserStore: useBrowserStore() };
}

function dialogOf(wrapper) {
  return wrapper.findComponent(ConfirmDialog);
}

describe("MarkReadButton — browser card kebab menu", () => {
  test("a collection card with children confirms before marking read", async () => {
    const item = collectionItem();
    const { wrapper, browserStore } = mountButton(item);
    expect(wrapper.vm.confirm).toBe(true);

    await wrapper.find(".codexListItem").trigger("click");

    expect(dialogOf(wrapper).vm.showDialog).toBe(true);
    expect(browserStore.setBookmarkFinished).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Mark Entire Publisher Read");
    expect(wrapper.text()).toContain("Youthful");

    await dialogOf(wrapper).vm.close("confirm");
    expect(browserStore.setBookmarkFinished).toHaveBeenCalledWith(item, true);
  });

  test("a comic card marks read immediately with no dialog", async () => {
    const item = comicItem();
    const { wrapper, browserStore } = mountButton(item);
    expect(wrapper.vm.confirm).toBe(false);
    expect(wrapper.vm.confirmText).toBe("");
    expect(wrapper.vm.markReadText).toBe("Mark Issue Read");

    await wrapper.find(".codexListItem").trigger("click");

    expect(dialogOf(wrapper).vm.showDialog).toBe(false);
    expect(browserStore.setBookmarkFinished).toHaveBeenCalledWith(item, true);
  });

  test("a single-child collection card does not confirm", () => {
    const { wrapper } = mountButton(collectionItem({ childCount: 1 }));
    expect(wrapper.vm.confirm).toBe(false);
  });

  test("a finished item offers unread and reuses the same gate", () => {
    const { wrapper } = mountButton(collectionItem({ finished: true }));
    expect(wrapper.vm.markReadText).toBe("Mark Entire Publisher Unread");
    expect(wrapper.vm.confirmText).toBe("Mark Unread");
  });
});

describe("MetadataControls — mark read item", () => {
  function mountControls(md) {
    const pinia = createTestingPinia({
      initialState: { metadata: { md } },
      stubActions: true,
    });
    return mount(MetadataControls, {
      global: {
        plugins: [pinia, vuetify],
        mocks: { $route: { name: "browser" } },
        stubs: { VDialog: VDialogStub },
      },
      props: { collection: md.collection },
    });
  }

  test("builds its item with childCount, the key the button reads", () => {
    const wrapper = mountControls({
      collection: "publishers",
      childCount: 12,
      finished: false,
      ids: [3],
      publisherList: [{ name: "Youthful" }],
    });
    const item = wrapper.vm.markReadItem;
    expect(item.childCount).toBe(12);
    expect(item.children).toBeUndefined();
    expect(wrapper.findComponent(MarkReadButton).vm.confirm).toBe(true);
  });

  test("a childless book falls back to one child and skips the dialog", () => {
    const wrapper = mountControls({
      collection: "comics",
      finished: false,
      ids: [7],
      name: "Captain Science #1",
    });
    expect(wrapper.vm.markReadItem.childCount).toBe(1);
    expect(wrapper.findComponent(MarkReadButton).vm.confirm).toBe(false);
  });
});

export default {};
