/*
 * The poll-interval input composes a valid Django duration, always.
 *
 * Clearing a part sets its model to ``null``, and ``String(null)`` is
 * ``"null"`` -- four characters, so ``padStart(3, "0")`` leaves it
 * alone and the emit was ``"null 01:00:00"``. The server rejects that
 * with a 400 the dialog rendered as raw JSON.
 *
 * Rules alone are not enough: they disable Submit but do not stop the
 * emit, so the composition is guarded too.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import DurationInput from "@/components/admin/create-update-dialog/duration-input.vue";
import vuetify from "@/plugins/vuetify";

const DURATION_RE = /^\d{3} \d{2}:\d{2}:\d{2}$/;

function mountInput(modelValue = "000 01:00:00") {
  return mount(DurationInput, {
    props: { label: "Poll Every", modelValue },
    global: { plugins: [vuetify] },
  });
}

function lastEmitted(wrapper) {
  const emitted = wrapper.emitted("update:modelValue");
  return emitted?.at(-1)?.[0];
}

describe("DurationInput", () => {
  test("parses the initial value into its parts", () => {
    const wrapper = mountInput("012 03:04:00");

    expect(wrapper.vm.days).toBe(12);
    expect(wrapper.vm.hours).toBe(3);
    expect(wrapper.vm.minutes).toBe(4);
  });

  test("composes a valid duration from its parts", async () => {
    const wrapper = mountInput();

    wrapper.vm.days = 2;
    wrapper.vm.hours = 3;
    wrapper.vm.minutes = 4;
    wrapper.vm.update();
    await wrapper.vm.$nextTick();

    expect(lastEmitted(wrapper)).toBe("002 03:04:00");
  });

  test("a cleared part never emits the string null", async () => {
    const wrapper = mountInput();

    // What v-number-input does when the field is emptied.
    wrapper.vm.days = null;
    wrapper.vm.update();
    await wrapper.vm.$nextTick();

    const emitted = lastEmitted(wrapper);
    expect(emitted).not.toContain("null");
    expect(emitted).toMatch(DURATION_RE);
  });

  test("every part cleared still composes a valid duration", async () => {
    const wrapper = mountInput();

    wrapper.vm.days = null;
    wrapper.vm.hours = null;
    wrapper.vm.minutes = null;
    wrapper.vm.update();
    await wrapper.vm.$nextTick();

    expect(lastEmitted(wrapper)).toBe("000 00:00:00");
  });

  test("a negative or unparseable part falls back to zero", () => {
    const wrapper = mountInput();

    expect(wrapper.vm.partOrZero(-5)).toBe(0);
    expect(wrapper.vm.partOrZero("")).toBe(0);
    expect(wrapper.vm.partOrZero("abc")).toBe(0);
    expect(wrapper.vm.partOrZero(undefined)).toBe(0);
  });

  test("zero is a legitimate value, not an empty one", () => {
    const wrapper = mountInput();

    expect(wrapper.vm.partOrZero(0)).toBe(0);
    expect(wrapper.vm.fieldsToDjangoDuration(0, 0, 30)).toBe("000 00:30:00");
  });

  test("each part carries a bounded rule", () => {
    const wrapper = mountInput();

    // The bounds match the :min/:max already on each control.
    expect(wrapper.vm.rules.days).toContainEqual(["$intRange", [0, 365]]);
    expect(wrapper.vm.rules.hours).toContainEqual(["$intRange", [0, 23]]);
    expect(wrapper.vm.rules.minutes).toContainEqual(["$intRange", [0, 59]]);
  });
});

export default {};
