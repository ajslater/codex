/*
 * Tests for the Tagging tab's Tag Write Errors panel.
 *
 * Behavior locked in here:
 *   - The panel renders only when the admin store has tag-write errors.
 *   - Each error shows its path and message.
 *   - The Clear button invokes the store's clearTagWriteErrors action.
 *   - The panel explains the read-only / permission cause.
 *   - A refused conversion links to the comic that already holds its name.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import TagWriteErrorsPanel from "@/components/admin/tabs/tag-write-errors-panel.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";

const ConfirmDialogStub = {
  name: "ConfirmDialog",
  emits: ["confirm"],
  render: () => null,
};

// Captures ``to`` so the link target can be asserted.
const RouterLinkStub = {
  name: "RouterLink",
  props: ["to"],
  template: "<a :title='$attrs.title'><slot /></a>",
};

const TWIN_PK = 77;

const ONE_ERROR = [
  {
    path: "/comics/broken.cbz",
    error: "Read-only file system",
    time: "2026-01-02T03:04:05Z",
  },
];

const TWIN_ERROR = [
  {
    path: "/comics/Foo.cbr",
    error: "already converted to Foo.cbz — edit that comic's tags instead",
    time: "2026-01-02T03:04:05Z",
    twinPk: TWIN_PK,
    twinName: "Foo.cbz",
  },
];

function mountPanel(tagWriteErrors = []) {
  const pinia = createTestingPinia({
    initialState: { admin: { tagWriteErrors } },
  });
  const wrapper = mount(TagWriteErrorsPanel, {
    global: {
      plugins: [pinia, vuetify],
      mocks: { $route: { hash: "" } },
      stubs: {
        ConfirmDialog: ConfirmDialogStub,
        DateTimeColumn: true,
        RouterLink: RouterLinkStub,
      },
    },
  });
  return { wrapper, store: useAdminStore() };
}

describe("AdminTagWriteErrorsPanel", () => {
  test("renders a row with the path and error when errors exist", () => {
    const { wrapper } = mountPanel(ONE_ERROR);
    expect(wrapper.find("#tagging-errors").exists()).toBe(true);
    expect(wrapper.findAll("tbody tr")).toHaveLength(1);
    expect(wrapper.text()).toContain("/comics/broken.cbz");
    expect(wrapper.text()).toContain("Read-only file system");
  });

  test("renders nothing when there are no errors", () => {
    const { wrapper } = mountPanel([]);
    expect(wrapper.find("#tagging-errors").exists()).toBe(false);
    expect(wrapper.find("table").exists()).toBe(false);
  });

  test("Clear invokes the clearTagWriteErrors store action", async () => {
    const { wrapper, store } = mountPanel(ONE_ERROR);
    wrapper.findComponent(ConfirmDialogStub).vm.$emit("confirm");
    await wrapper.vm.$nextTick();
    expect(store.clearTagWriteErrors).toHaveBeenCalled();
  });

  test("explains the read-only / permission cause", () => {
    const { wrapper } = mountPanel(ONE_ERROR);
    expect(wrapper.text()).toContain("failed to have their tags written");
  });

  test("a refused conversion links to the comic it became", () => {
    const { wrapper } = mountPanel(TWIN_ERROR);

    const link = wrapper.findComponent(RouterLinkStub);
    expect(link.exists()).toBe(true);
    expect(link.props("to")).toStrictEqual({
      name: "reader",
      params: { pk: TWIN_PK },
    });
    expect(link.text()).toBe("Foo.cbz");
    expect(link.attributes("title")).toBe("Open Foo.cbz");
  });

  test("an error with no twin gets no link", () => {
    const { wrapper } = mountPanel(ONE_ERROR);
    expect(wrapper.findComponent(RouterLinkStub).exists()).toBe(false);
  });
});

export default {};
