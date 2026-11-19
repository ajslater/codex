/*
 * The copy target is a real button.
 *
 * It was a ``<div>`` with a click handler and no role or key handler, and
 * it is now the only way to copy a secret shown once: keyboard and screen
 * reader users could not reach it.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ClipBoard from "@/components/clipboard.vue";
import vuetify from "@/plugins/vuetify";

describe("ClipBoard", () => {
  test("is a focusable button that does not submit a form", () => {
    const wrapper = mount(ClipBoard, {
      props: { tooltip: "Copy", title: "Key", text: "secret" },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.element.tagName).toBe("BUTTON");
    expect(wrapper.attributes("type")).toBe("button");
    expect(wrapper.find("div").exists()).toBe(false);
  });
});
