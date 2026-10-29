/*
 * The Add Library folder tree.
 *
 * Behavior locked in here:
 *   - It opens on the server's default folder with nothing chosen, since
 *     that folder is the newest library's parent and no valid choice.
 *   - Opening a folder lists its subfolders, dropping the server's "..";
 *     an empty folder becomes a leaf; past FOLDER_CAP the rest collapse
 *     into one disabled "type the path" leaf.
 *   - A folder an existing library covers is disabled and says why.
 *   - Choosing a folder fills the path field, which emits ``change``.
 *   - Enter on a typed path re-roots there and chooses it; a bad path shows
 *     the server's reason under the field.
 *   - Parent folder re-roots one level up and keeps the old root, open,
 *     with what it already loaded.
 *   - Show Hidden Folders refetches.
 *   - A folder that fails to load says so on its node, not in the form's
 *     shared errors.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ServerFolderTree, {
  FOLDER_CAP,
} from "@/components/admin/create-update-dialog/server-folder-tree.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const LISTINGS = Object.freeze({
  "/comics": {
    rootFolder: "/comics",
    parentFolder: "/",
    folders: ["..", "DC", "empty", "Marvel"],
  },
  "/comics/DC": {
    rootFolder: "/comics/DC",
    parentFolder: "/comics",
    folders: ["..", "Batman"],
  },
  "/comics/empty": {
    rootFolder: "/comics/empty",
    parentFolder: "/comics",
    folders: [".."],
  },
  "/": { rootFolder: "/", parentFolder: null, folders: ["comics", "tmp"] },
});

function child(vm, title, node = vm.items[0]) {
  return node.children.find((item) => item.title === title);
}

function mountTree({ libraries = [], listings = LISTINGS } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { isStaff: true } },
      admin: { libraries },
    },
  });
  const store = useAdminStore(pinia);
  // No path asks for the server's default folder.
  store.fetchFolders.mockImplementation((path = "/comics") => {
    const listing = listings[path];
    return listing
      ? Promise.resolve(structuredClone(listing))
      : Promise.reject(new Error("Not a directory"));
  });
  const wrapper = mount(ServerFolderTree, {
    attrs: { label: "Library Folder" },
    global: { plugins: [vuetify, pinia] },
  });
  return { wrapper, vm: wrapper.vm, store };
}

describe("AdminServerFolderTree — opening", () => {
  test("roots at the default folder with nothing chosen", async () => {
    const { wrapper, vm, store } = mountTree();
    await flushPromises();
    expect(wrapper.findComponent({ name: "VTreeview" }).exists()).toBe(true);
    expect(store.fetchFolders).toHaveBeenCalledWith(undefined, false);
    expect(vm.items[0].value).toBe("/comics");
    expect(vm.opened).toEqual(["/comics"]);
    expect(vm.activated).toEqual([]);
    expect(vm.path).toBe("");
    expect(wrapper.find("label").text()).toBe("Library Folder");
  });

  test("lists subfolders without the server's '..'", async () => {
    const { vm } = mountTree();
    await flushPromises();
    expect(vm.items[0].children.map(({ title }) => title)).toEqual([
      "DC",
      "empty",
      "Marvel",
    ]);
    expect(child(vm, "DC").value).toBe("/comics/DC");
  });

  test("loading a folder fills its children; an empty one is a leaf", async () => {
    const { vm } = mountTree();
    await flushPromises();
    await vm.loadChildren(child(vm, "DC"));
    expect(child(vm, "DC").children.map(({ value }) => value)).toEqual([
      "/comics/DC/Batman",
    ]);
    const empty = child(vm, "empty");
    await vm.loadChildren(empty);
    expect(empty).not.toHaveProperty("children");
  });

  test("past the cap the rest become one disabled leaf", async () => {
    const many = Array.from({ length: FOLDER_CAP + 7 }, (_, i) => `f${i}`);
    const { vm } = mountTree({
      listings: {
        "/comics": { rootFolder: "/comics", parentFolder: "/", folders: many },
      },
    });
    await flushPromises();
    const children = vm.items[0].children;
    expect(children).toHaveLength(FOLDER_CAP + 1);
    const last = children.at(-1);
    expect(last.title).toBe("7 more folders, type the path above");
    expect(last.props.disabled).toBe(true);
    expect(last).not.toHaveProperty("children");
  });

  test("a folder an existing library covers is disabled with a reason", async () => {
    const { vm } = mountTree({ libraries: [{ path: "/comics/Marvel" }] });
    await flushPromises();
    const marvel = child(vm, "Marvel");
    expect(marvel.props).toEqual({
      disabled: true,
      subtitle: "Already a library",
    });
    expect(marvel).not.toHaveProperty("children");
    expect(child(vm, "DC").props).toBeUndefined();
  });
});

describe("AdminServerFolderTree — choosing", () => {
  test("choosing a folder fills the path and emits change", async () => {
    const { wrapper, vm } = mountTree();
    await flushPromises();
    vm.activated = ["/comics/DC"];
    await flushPromises();
    expect(vm.path).toBe("/comics/DC");
    expect(wrapper.emitted("change").at(-1)).toEqual(["/comics/DC"]);
  });

  test("Enter on a typed path re-roots there and chooses it", async () => {
    const { wrapper, vm } = mountTree();
    await flushPromises();
    const input = wrapper.find("input");
    await input.setValue("/comics/DC");
    await input.trigger("keydown", { key: "Enter" });
    await flushPromises();
    expect(vm.items[0].value).toBe("/comics/DC");
    expect(vm.activated).toEqual(["/comics/DC"]);
    expect(wrapper.emitted("change").at(-1)).toEqual(["/comics/DC"]);
  });

  test("Enter on a bad path shows the reason and keeps the tree", async () => {
    const { wrapper, vm } = mountTree();
    await flushPromises();
    const input = wrapper.find("input");
    await input.setValue("/nope");
    await input.trigger("keydown", { key: "Enter" });
    await flushPromises();
    expect(vm.pathErrors).toEqual(["Not a directory"]);
    expect(wrapper.text()).toContain("Not a directory");
    expect(vm.items[0].value).toBe("/comics");
  });
});

describe("AdminServerFolderTree — navigating", () => {
  test("Parent re-roots up and keeps the old root's loaded children", async () => {
    const { wrapper, vm } = mountTree();
    await flushPromises();
    await vm.loadChildren(child(vm, "DC"));
    vm.opened = ["/comics", "/comics/DC"];
    await wrapper.find('button[aria-label="Parent folder"]').trigger("click");
    await flushPromises();
    expect(vm.items[0].value).toBe("/");
    const comics = child(vm, "comics");
    expect(comics.title).toBe("comics");
    expect(child(vm, "Batman", child(vm, "DC", comics)).value).toBe(
      "/comics/DC/Batman",
    );
    expect(vm.opened).toEqual(["/", "/comics", "/comics/DC"]);
    expect(vm.parentFolder).toBeNull();
  });

  test("Show Hidden Folders refetches the chosen folder", async () => {
    const { vm, store } = mountTree();
    await flushPromises();
    vm.activated = ["/comics/DC"];
    await flushPromises();
    vm.showHidden = true;
    await flushPromises();
    expect(store.fetchFolders).toHaveBeenLastCalledWith("/comics/DC", true);
    expect(vm.items[0].value).toBe("/comics/DC");
    expect(vm.activated).toEqual(["/comics/DC"]);
  });

  test("a folder that fails to load says so on its node only", async () => {
    const { vm } = mountTree();
    await flushPromises();
    const marvel = child(vm, "Marvel");
    await vm.loadChildren(marvel);
    expect(marvel.props).toEqual({ subtitle: "Not a directory" });
    expect(marvel).not.toHaveProperty("children");
    expect(vm.pathErrors).toEqual([]);
    expect(useCommonStore().setErrors).not.toHaveBeenCalled();
  });
});

export default {};
