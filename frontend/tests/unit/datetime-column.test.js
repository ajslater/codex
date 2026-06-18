/*
 * Tests for the admin tables' DateTimeColumn.
 *
 * Behavior locked in here:
 *   - Null/empty/pre-2000 timestamps render "Never".
 *   - A real timestamp renders the formatted date.
 *   - Regression: when the dttm prop changes on a live component
 *     instance (websocket-driven table refetch reuses the row's
 *     component), the displayed date follows the prop. Previously
 *     ``date`` was snapshotted once in ``data()``, so a library's
 *     Last Poll column stayed at the epoch after its first import
 *     finished until a full browser reload.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import vuetify from "@/plugins/vuetify";

function mountColumn(dttm) {
  const pinia = createTestingPinia({
    initialState: {
      browser: { settings: { twentyFourHourTime: true } },
    },
  });
  return mount(DateTimeColumn, {
    props: { dttm },
    global: { plugins: [pinia, vuetify] },
  });
}

describe("DateTimeColumn", () => {
  test("renders Never for a null timestamp", () => {
    const wrapper = mountColumn(null);
    expect(wrapper.text()).toBe("Never");
  });

  test("renders Never for a pre-2000 timestamp", () => {
    const wrapper = mountColumn("1970-01-01T00:00:00Z");
    expect(wrapper.text()).toBe("Never");
  });

  test("renders the formatted date for a real timestamp", () => {
    const wrapper = mountColumn("2026-06-11T12:34:56Z");
    expect(wrapper.text()).not.toContain("Never");
    expect(wrapper.text()).toContain("2026");
  });

  test("updates the rendered date when the dttm prop changes", async () => {
    const wrapper = mountColumn(null);
    expect(wrapper.text()).toBe("Never");

    await wrapper.setProps({ dttm: "2026-06-11T12:34:56Z" });

    expect(wrapper.text()).not.toContain("Never");
    expect(wrapper.text()).not.toContain("1970");
    expect(wrapper.text()).toContain("2026");
  });
});

export default {};
