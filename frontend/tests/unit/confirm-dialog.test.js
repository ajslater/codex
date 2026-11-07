/*
 * ConfirmDialog's two modes.
 *
 * Behavior locked in here:
 *   - With no modelValue it manages itself: its own button opens it, and
 *     Confirm emits ``confirm`` and closes it.
 *   - With a modelValue it is controlled from outside, as for a dialog
 *     launched from a menu: it renders no activator, shows only while the
 *     model is true, and reports every close through ``update:modelValue``,
 *     a scrim click or Escape included.
 *
 * ``v-dialog`` is stubbed so the overlay/teleport machinery happy-dom lacks
 * stays out of it; the stub keeps the activator slot and the open state.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import vuetify from "@/plugins/vuetify";

const VDialogStub = Object.freeze({
  name: "VDialog",
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: `<div class="dialogStub">
    <slot name="activator" :props="{ onClick: () => $emit('update:modelValue', true) }" />
    <slot v-if="modelValue" />
  </div>`,
});

const PROPS = Object.freeze({
  titleText: "Poll for updated comics",
  text: "/comics",
  confirmText: "Poll Library",
  buttonText: "Poll",
});

function confirmButton(wrapper) {
  return wrapper.find(".confirmButton");
}

function mountDialog(props = {}) {
  return mount(ConfirmDialog, {
    props: { ...PROPS, ...props },
    global: { plugins: [vuetify], stubs: { VDialog: VDialogStub } },
  });
}

describe("ConfirmDialog — self-managed", () => {
  test("its own button opens it and Confirm closes it", async () => {
    const wrapper = mountDialog();
    expect(wrapper.vm.controlled).toBe(false);
    expect(confirmButton(wrapper).exists()).toBe(false);

    await wrapper.find("button").trigger("click");
    expect(wrapper.vm.showDialog).toBe(true);

    await confirmButton(wrapper).trigger("click");
    expect(wrapper.emitted("confirm")).toHaveLength(1);
    expect(wrapper.vm.showDialog).toBe(false);
  });
});

describe("ConfirmDialog — controlled", () => {
  test("renders no activator and follows the model", async () => {
    const wrapper = mountDialog({ modelValue: false });
    expect(wrapper.vm.controlled).toBe(true);
    expect(wrapper.find("button").exists()).toBe(false);

    await wrapper.setProps({ modelValue: true });
    expect(confirmButton(wrapper).exists()).toBe(true);
  });

  test("Confirm emits confirm, then asks to close", async () => {
    const wrapper = mountDialog({ modelValue: true });
    await confirmButton(wrapper).trigger("click");
    expect(wrapper.emitted("confirm")).toHaveLength(1);
    expect(wrapper.emitted("update:modelValue")).toEqual([[false]]);
  });

  test("a scrim click or Escape reports the close without confirming", async () => {
    const wrapper = mountDialog({ modelValue: true });
    wrapper.findComponent(VDialogStub).vm.$emit("update:modelValue", false);
    await wrapper.vm.$nextTick();
    expect(wrapper.emitted("update:modelValue")).toEqual([[false]]);
    expect(wrapper.emitted("confirm")).toBeUndefined();
  });
});

export default {};
