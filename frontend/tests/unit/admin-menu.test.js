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

function mountMenu({
  tagWriteErrors = [],
  pendingPrompts = [],
  failedImports = [],
  failedImportsSeenAt = "",
} = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { isStaff: true } },
      admin: { tagWriteErrors, failedImports, failedImportsSeenAt },
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
      pendingPrompts: [
        { fingerprint: "a", pk: 1 },
        { fingerprint: "b", pk: 2 },
      ],
    });

    const items = wrapper.findAll(".promptsLink");
    expect(items).toHaveLength(1);
    expect(items[0].text()).toContain("2 Matches to Review");
  });

  // One question can hold a whole series, so the count that matters is how
  // many comics are waiting, not how many dialogs' worth of questions.
  test("counts every comic a series-level prompt covers", () => {
    const wrapper = mountMenu({
      pendingPrompts: [
        { fingerprint: "a", pk: 1, comics: [{ pk: 1 }, { pk: 2 }, { pk: 3 }] },
      ],
    });

    expect(wrapper.findAll(".promptsLink")[0].text()).toContain(
      "3 Matches to Review",
    );
  });
});

describe("AdminMenu failed imports link", () => {
  const unseen = [
    { path: "/comics/bad.cbz", createdAt: "2026-09-20T00:00:00Z" },
  ];

  test("no link when there are no failed imports", () => {
    const wrapper = mountMenu();

    expect(wrapper.findAll(".failedImportsLink")).toHaveLength(0);
  });

  test("link is present and colored while failures are unseen", () => {
    const wrapper = mountMenu({ failedImports: unseen });

    const link = wrapper.find(".failedImportsLink");
    expect(link.exists()).toBe(true);
    expect(link.classes()).toContain("failedImportsUnseen");
  });

  test("link survives Clear Warning, without the error color", () => {
    // The reported symptom: clearing the warning hid the only way back
    // to a table that was still there.
    const wrapper = mountMenu({
      failedImports: unseen,
      failedImportsSeenAt: "2026-09-21T00:00:00Z",
    });

    const link = wrapper.find(".failedImportsLink");
    expect(link.exists()).toBe(true);
    expect(link.classes()).not.toContain("failedImportsUnseen");
  });
});
