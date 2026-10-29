<template>
  <div id="folderTree">
    <div class="folderPathRow">
      <v-text-field
        v-model="path"
        v-bind="$attrs"
        :error-messages="pathErrors"
        hide-details="auto"
        variant="filled"
        @keydown.enter.prevent.stop="onEnter"
        @update:model-value="pathErrors = []"
      />
      <v-btn
        :icon="mdiFolderArrowUpOutline"
        :disabled="!parentFolder"
        aria-label="Parent folder"
        title="Parent folder"
        variant="text"
        @click="goToParent"
      />
    </div>
    <div class="folderTreeBox">
      <v-treeview
        v-model:activated="activated"
        v-model:opened="opened"
        :items="items"
        :load-children="loadChildren"
        activatable
        mandatory
        open-on-click
        density="compact"
        aria-label="Server folders"
      >
        <template #prepend="{ item, isOpen }">
          <v-icon :icon="folderIcon(item, isOpen)" size="small" />
        </template>
      </v-treeview>
    </div>
    <v-checkbox
      v-model="showHidden"
      density="compact"
      class="showHidden"
      hide-details="auto"
      label="Show Hidden Folders"
    />
  </div>
</template>

<script>
import {
  mdiBookshelf,
  mdiFolderArrowUpOutline,
  mdiFolderOpenOutline,
  mdiFolderOutline,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { isPathParent } from "@/components/admin/create-update-dialog/path-parent";
import { useAdminStore } from "@/stores/admin";

/*
 * VTreeview renders every child of an open node, with no virtual scroll,
 * and each child folder is a whole expandable group. In a production build
 * 200 of them open in about 0.6s; 500 took up to 1.5s, and indent lines
 * cost another third. Past this many, the rest are reached by typing the
 * path.
 */
export const FOLDER_CAP = 200;
// The server's "go up" entry; the Parent folder button replaces it.
const PARENT_ENTRY = "..";

const joinPath = (parent, name) =>
  parent.endsWith("/") || parent.endsWith("\\")
    ? parent + name
    : `${parent}/${name}`;

export default {
  name: "AdminServerFolderTree",
  // The parent's rules, label and autofocus belong on the path field.
  inheritAttrs: false,
  emits: ["change"],
  data() {
    return {
      mdiFolderArrowUpOutline,
      // The path field is the source of truth; the tree only fills it.
      path: "",
      pathErrors: [],
      parentFolder: null,
      items: [],
      activated: [],
      opened: [],
      showHidden: false,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      libraryPaths: (state) => (state.libraries || []).map(({ path }) => path),
    }),
  },
  watch: {
    path(to) {
      this.$emit("change", to);
    },
    activated(to) {
      if (to?.[0]) {
        this.path = to[0];
      }
    },
    showHidden() {
      // Re-root at the chosen folder, keeping it chosen, or at the root.
      const chosen = this.activated[0];
      this.reRoot(chosen || this.items[0]?.value, {
        activate: Boolean(chosen),
      });
    },
  },
  mounted() {
    /*
     * No path: the server's default folder. Nothing is chosen yet, since
     * that folder is the newest library's parent and no valid choice.
     */
    this.reRoot();
  },
  methods: {
    ...mapActions(useAdminStore, ["fetchFolders"]),
    libraryContaining(folder) {
      return this.libraryPaths.find((path) => isPathParent(path, folder));
    },
    makeNode(folder, title = folder) {
      const library = this.libraryContaining(folder);
      if (library) {
        // A folder an existing library covers can't be a new library.
        const subtitle =
          library === folder ? "Already a library" : `Inside ${library}`;
        return {
          title,
          value: folder,
          library: true,
          props: { disabled: true, subtitle },
        };
      }
      return { title, value: folder, children: [] };
    },
    fillChildren(node, folders) {
      const names = folders.filter((name) => name !== PARENT_ENTRY);
      if (names.length === 0) {
        // An empty folder is a leaf: no chevron to open into nothing.
        delete node.children;
        return;
      }
      node.children = names
        .slice(0, FOLDER_CAP)
        .map((name) => this.makeNode(joinPath(node.value, name), name));
      const more = names.length - FOLDER_CAP;
      if (more > 0) {
        node.children.push({
          title: `${more} more folders, type the path above`,
          value: `${node.value}\0more`,
          props: { disabled: true },
        });
      }
    },
    setRoot({ rootFolder, parentFolder, folders }, { activate = false } = {}) {
      const root = { title: rootFolder, value: rootFolder, children: [] };
      this.fillChildren(root, folders);
      this.parentFolder = parentFolder;
      this.items = [root];
      this.opened = [rootFolder];
      if (activate) {
        this.activated = [rootFolder];
      }
      this.pathErrors = [];
    },
    async reRoot(folder, options) {
      try {
        this.setRoot(await this.fetchFolders(folder, this.showHidden), options);
      } catch (error) {
        this.pathErrors = [error.message];
      }
    },
    async loadChildren(node) {
      try {
        const { folders } = await this.fetchFolders(
          node.value,
          this.showHidden,
        );
        this.fillChildren(node, folders);
      } catch (error) {
        // The failure stays on the node; it isn't the path field's error.
        node.props = { subtitle: error.message };
        delete node.children;
      }
    },
    onEnter() {
      if (this.path) {
        this.reRoot(this.path, { activate: true });
      }
    },
    async goToParent() {
      const oldRoot = this.items[0];
      let listing;
      try {
        listing = await this.fetchFolders(this.parentFolder, this.showHidden);
      } catch (error) {
        this.pathErrors = [error.message];
        return;
      }
      const opened = this.opened;
      this.setRoot(listing);
      // Keep the old root, open with what it already loaded.
      const root = this.items[0];
      const index = (root.children || []).findIndex(
        ({ value }) => value === oldRoot.value,
      );
      const entry = root.children?.[index];
      if (entry && !entry.library) {
        root.children.splice(index, 1, { ...oldRoot, title: entry.title });
      }
      this.opened = [root.value, ...opened];
    },
    folderIcon(item, isOpen) {
      if (item.library) {
        return mdiBookshelf;
      }
      // A leaf can be "open" from a click, but there is nothing in it.
      return isOpen && item.children ? mdiFolderOpenOutline : mdiFolderOutline;
    },
  },
};
</script>

<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  #folderTree {
    border-radius: 5px;
    background-color: rgb(var(--v-theme-surface));
  }

  .folderPathRow {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  // px, not em: a v-dialog sizes its content in px.
  .folderTreeBox {
    height: 280px;
    overflow-y: auto;
  }

  .showHidden :deep(.v-label) {
    color: rgb(var(--v-theme-text-secondary));
  }
}
</style>
