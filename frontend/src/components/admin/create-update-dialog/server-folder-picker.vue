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
      :items="folders"
      :menu-props="{ maxHeight: '370px' }"
      validate-on="blur"
      variant="filled"
      @blur="onBlur"
      @click:clear="onClear"
      @keydown.enter.prevent.stop="onKeyDownEnter"
    >
      <template #item="{ internalItem, props }">
        <v-list-item
          v-bind="props"
          :title="internalItem.title"
          :value="internalItem.value"
          @click="onItemClick(internalItem.value)"
        />
      </template>
    </v-combobox>
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
import { mapActions, mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

export default {
  name: "AdminServerFolderPicker",
  emits: ["change"],
  data() {
    return {
      menuOpen: false,
      originalPath: "",
      path: "",
      showHidden: false,
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
    appendOuterIcon() {
      return this.showHidden ? this.mdiFolderHidden : this.mdiFolderOutline;
    },
    showHiddenTooltipPrefix() {
      return this.showHidden ? "Hide" : "Show";
    },
  },
  mounted() {
    /*
     * Delay initial load so the dialog transition completes
     * and the combobox has its final position for menu placement.
     */
    setTimeout(() => {
      this.loadFolders()
        .then(() => {
          this.path = this.rootFolder;
          this.originalPath = this.rootFolder;
          return true;
        })
        .catch(console.warn);
    }, 200);
  },
  methods: {
    ...mapActions(useAdminStore, ["clearFolders", "loadFolders"]),
    ...mapActions(useCommonStore, ["clearErrors"]),
    change(path, { openMenu = false } = {}) {
      let relativePath;
      if (path) {
        relativePath =
          path.startsWith("/") || path.startsWith("\\")
            ? path
            : [this.rootFolder, path].join("/");
      } else {
        relativePath = this.rootFolder;
      }
      this.clearErrors();
      this.loadFolders(relativePath, this.showHidden)
        .then(() => {
          if (this.formErrors.length === 0) {
            this.path = this.rootFolder;
            this.$emit("change", this.path);
          }
          if (openMenu && this.folders.length > 0) {
            /*
             * Wait for Vue to process the path change, then wait for
             * Vuetify's internal reactions to the v-model update to
             * finish before opening the menu.
             */
            this.menuOpen = false;
            this.$nextTick(() => {
              setTimeout(() => {
                this.menuOpen = true;
              }, 100);
            });
          }
        })
        .catch(console.warn);
    },
    onBlur() {
      this.change(this.path);
    },
    onClear() {
      this.clearFolders(this.originalPath)
        .then(() => {
          return this.change(this.originalPath);
        })
        .catch(console.error);
    },
    onKeyDownEnter() {
      this.change(this.path, { openMenu: true });
    },
    onItemClick(path) {
      this.change(path);
    },
  },
};
</script>

<style scoped lang="scss">
#folderPicker {
  border-radius: 5px;
  background-color: rgb(var(--v-theme-surface));
}

.showHidden :deep(.v-label) {
  color: rgb(var(--v-theme-textSecondary));
}
</style>
