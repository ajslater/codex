/*
 * Tests for the sidebar admin menu's notification list items.
 *
 * Each error kind gets exactly one list item: tag-write errors and failed
 * imports link to their admin panels, pending online-tag prompts open the
 * Match Review dialog. Multiple errors of one kind are represented in the
 * admin tables, never as extra sidebar items.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import AdminMenu from "@/components/admin/drawer/admin-menu.vue";
import vuetify from "@/plugins/vuetify";

const AdminStatusListStub = { name: "AdminStatusList", template: "<div />" };

function mountMenu({ tagWriteErrors = [], pendingPrompts = [] } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { isStaff: true } },
      admin: { tagWriteErrors },
      onlineTag: { pendingPrompts },
    },
  });
  return mount(AdminMenu, {
    global: {
      plugins: [vuetify, pinia],
      stubs: { AdminStatusList: AdminStatusListStub, RouterLink: true },
      mocks: {
        $router: { currentRoute: { value: { name: "browser" } } },
      },
    },
  });
}

describe("AdminMenu", () => {
  test("no error items when nothing is wrong", () => {
    const wrapper = mountMenu();

    expect(wrapper.findAll(".tagWriteErrorsLink")).toHaveLength(0);
    expect(wrapper.findAll(".promptsLink")).toHaveLength(0);
  });

  test("exactly one tag-write-errors item regardless of error count", () => {
    const wrapper = mountMenu({
      tagWriteErrors: [
        { path: "/comics/a.cbz", error: "read-only" },
        { path: "/comics/b.cbz", error: "read-only" },
        { path: "/comics/c.cbz", error: "corrupt" },
      ],
    });

    expect(wrapper.findAll(".tagWriteErrorsLink")).toHaveLength(1);
  });

  test("exactly one prompts item regardless of prompt count", () => {
    const wrapper = mountMenu({
      pendingPrompts: [{ fingerprint: "a" }, { fingerprint: "b" }],
    });

    const items = wrapper.findAll(".promptsLink");
    expect(items).toHaveLength(1);
    expect(items[0].text()).toContain("2 Matches to Review");
  });
});
