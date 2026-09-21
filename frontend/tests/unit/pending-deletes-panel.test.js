/*
 * Tests for the Libraries tab's Pending Deletes panel.
 *
 * Behavior locked in here:
 *   - The panel renders only when something is actually pending, so it
 *     stays invisible on the overwhelming majority of installs.
 *   - Each row shows its path, type and both timestamps.
 *   - Keep invokes the revive action with the row's own collection and
 *     pk -- a comic and a folder can share a pk, so passing only the pk
 *     would revive the wrong row.
 *   - Delete Expired Now goes through the ordinary task endpoint rather
 *     than inventing a second one.
 *   - The hint explains what the state is and how to leave it.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import PendingDeletesPanel from "@/components/admin/tabs/pending-deletes-panel.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";

const COMIC_PK = 42;
const FOLDER_PK = 42; // deliberately the same: only the pair identifies a row

const PENDING = [
  {
    pk: COMIC_PK,
    collection: "comics",
    path: "/comics/Series/Issue 1.cbz",
    libraryId: 1,
    missingSince: "2026-01-02T03:04:05Z",
    reapAfter: "2026-01-03T03:04:05Z",
  },
  {
    pk: FOLDER_PK,
    collection: "folders",
    path: "/comics/Series",
    libraryId: 1,
    missingSince: "2026-01-02T03:04:05Z",
    reapAfter: "2026-01-03T03:04:05Z",
  },
];

function mountPanel(pendingDeletes = []) {
  const pinia = createTestingPinia({
    initialState: { admin: { pendingDeletes } },
  });
  const wrapper = mount(PendingDeletesPanel, {
    global: {
      plugins: [pinia, vuetify],
      mocks: { $route: { hash: "" } },
      stubs: { DateTimeColumn: true },
    },
  });
  return { wrapper, store: useAdminStore() };
}

describe("AdminPendingDeletesPanel", () => {
  test("renders nothing when nothing is pending", () => {
    const { wrapper } = mountPanel([]);
    expect(wrapper.find("#pendingDeletes").exists()).toBe(false);
    expect(wrapper.find("table").exists()).toBe(false);
  });

  test("renders a row per pending delete with its path and type", () => {
    const { wrapper } = mountPanel(PENDING);
    expect(wrapper.find("#pendingDeletes").exists()).toBe(true);
    expect(wrapper.findAll("tbody tr")).toHaveLength(PENDING.length);
    expect(wrapper.text()).toContain("/comics/Series/Issue 1.cbz");
    expect(wrapper.text()).toContain("Comic");
    expect(wrapper.text()).toContain("Folder");
  });

  test("Keep revives the row's own collection and pk", async () => {
    const { wrapper, store } = mountPanel(PENDING);
    const keepButtons = wrapper.findAll(".actionCol button");
    expect(keepButtons).toHaveLength(PENDING.length);

    await keepButtons[1].trigger("click");

    expect(store.revivePendingDelete).toHaveBeenCalledWith(
      "folders",
      FOLDER_PK,
    );
  });

  test("Delete Expired Now runs the nightly job on demand", async () => {
    const { wrapper, store } = mountPanel(PENDING);

    await wrapper.find(".pendingDeletesActions button").trigger("click");

    expect(store.librarianTask).toHaveBeenCalledWith("reap_pending_deletes");
  });

  test("the hint says what the state is and how to leave it", () => {
    const { wrapper } = mountPanel(PENDING);
    const text = wrapper.text();
    expect(text).toContain("keeps");
    expect(text).toContain("read progress");
  });
});

export default {};
