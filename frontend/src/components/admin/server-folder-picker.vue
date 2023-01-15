<template>
  <div id="folderPicker">
    <v-combobox
      ref="folderPicker"
      v-model="path"
      v-model:menu="menuOpen"
      v-bind="$attrs"
      aria-label="Library folder"
      clearable
      :error-messages="formErrors"
      full-width
      hide-details="auto"
      hide-selected
      :items="folders"
      :menu-props="{ maxHeight: '300px' }"
      no-filter
      validate-on="blur"
      variant="filled"
      @blur="onBlur"
      @click:clear="onClear"
      @focus="onFocus"
      @update:model-value="onUpdateModelValue"
    />
    <v-checkbox
      v-model="showHidden"
      class="showHidden"
      hide-details="auto"
      label="Show Hidden Folders"
    />
  </div>
</template>

<script>
import { mdiFileTree, mdiFolderHidden, mdiFolderOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

export default {
  name: "AdminServerFolderPicker",
  emits: ["change", "menu"],
  data() {
    return {
      path: "",
      originalPath: "",
      showHidden: false,
      menuOpen: false,
      mdiFileTree,
      mdiFolderHidden,
      mdiFolderOutline,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      folders: (state) => state.folderPicker.folders,
      rootFolder: (state) => state.folderPicker.rootFolder,
    }),
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
    }),
    appendOuterIcon: function () {
      return this.showHidden ? this.mdiFolderHidden : this.mdiFolderOutline;
    },
    showHiddenTooltipPrefix: function () {
      return this.showHidden ? "Hide" : "Show";
    },
  },
  watch: {
    menuOpen(to) {
      if (to) {
        this.$emit("menu", to);
      }
    },
  },
  created() {
    this.loadFolders()
      .then(() => {
        this.path = this.rootFolder;
        this.originalPath = this.rootFolder;
        return true;
      })
      .catch(console.warn);
  },
  methods: {
    ...mapActions(useAdminStore, ["loadFolders"]),
    ...mapActions(useCommonStore, ["clearErrors"]),
    change: function (path) {
      const relativePath = path
        ? path.startsWith("/")
          ? path
          : [this.rootFolder, path].join("/")
        : this.rootFolder;
      const isMenuActive = this.$refs.folderPicker.isMenuActive; // TODO try to replace without ref
      this.clearErrors();
      this.loadFolders(relativePath, this.showHidden)
        .then(() => {
          if (this.formErrors.length > 0) {
            return;
          }
          this.path = this.rootFolder;
          // This keeps the menu scrolling after a menu click.
          this.$refs.folderPicker.isMenuActive = isMenuActive;
          return this.$emit("change", this.path);
        })
        .catch(console.warn);
    },
    toggleMenu: function (val) {
      if (val === undefined) {
        val = !this.menuOpen;
      }
      this.menuOpen = val;
      this.$refs.folderPicker.isMenuActive = val;
    },
    toggleHidden: function () {
      this.showHidden = !this.showHidden;
      this.change(this.path);
    },
    onAppend() {
      this.toggleMenu();
    },
    onBlur() {
      this.focus = false;
      this.toggleMenu(false);
      this.change(this.path);
    },
    onFocus() {
      this.focus = true;
    },
    onUpdateModelValue(event) {
      if (!this.focus) {
        this.change(event);
      }
    },
    onClear() {
      this.clearErrors();
      this.change(this.originalPath);
    },
  },
};
</script>

<style scoped lang="scss">
#folderPicker {
  background-color: rgb(var(--v-theme-surface));
  border-radius: 5px;
}
:deep(.showHidden .v-label) {
  color: rgb(var(--v-theme-textSecondary));
}
</style>
