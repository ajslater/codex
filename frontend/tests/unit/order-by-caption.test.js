/*
 * Tests for the browser card's order-by caption.
 *
 * Behavior locked in here:
 *   - "reprints" order_value is the JSON array the table cell renders,
 *     never the composed key the rows are sorted by; comic cards join
 *     the labels, collection cards show nothing because they sort by a
 *     fallback the caption can't represent.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import OrderByCaption from "@/components/browser/card/order-by-caption.vue";
import vuetify from "@/plugins/vuetify";

function mountCaption(orderBy, item) {
  const pinia = createTestingPinia({
    initialState: { browser: { settings: { orderBy } } },
  });
  return mount(OrderByCaption, {
    props: { item },
    global: { plugins: [pinia, vuetify] },
  });
}

describe("order by caption", () => {
  test("reprint series joins the label list on a comic card", () => {
    const wrapper = mountCaption("reprints", {
      orderValue: JSON.stringify(["Crossover v2", "Otra Serie (es)"]),
      collection: "comics",
    });
    expect(wrapper.text()).toBe("Crossover v2, Otra Serie (es)");
  });

  test("reprint series shows nothing on a collection card", () => {
    const wrapper = mountCaption("reprints", {
      orderValue: JSON.stringify(["Crossover"]),
      collection: "series",
    });
    expect(wrapper.text()).toBe("");
  });
});
