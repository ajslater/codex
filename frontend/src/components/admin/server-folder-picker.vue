<template>
  <div id="folderPicker">
    <v-combobox
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
      @keydown.enter="onKeyDownEnter"
    >
      <template #item="{ item, props }">
        <v-list-item
          v-bind="props"
          :title="item.title"
          :value="item.value"
          @click="onItemClick(item.value)"
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
  emits: ["change", "menu"],
  data() {
    return {
      path: "",
      originalPath: "",
      showHidden: false,
      menuOpen: false,
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
    ...mapActions(useAdminStore, ["clearFolders", "loadFolders"]),
    ...mapActions(useCommonStore, ["clearErrors"]),
    change: function (path) {
      const relativePath = path
        ? path.startsWith("/") || path.startsWith("\\")
          ? path
          : [this.rootFolder, path].join("/")
        : this.rootFolder;
      const isMenuOpen = this.menuOpen;
      this.clearErrors();
      this.loadFolders(relativePath, this.showHidden)
        .then(() => {
          // menuProps: closeOnContentClick doesn't seem to work.
          //  menu still flashes, not great.
          this.menuOpen = isMenuOpen;
          let changePath = "";
          if (this.formErrors.length === 0) {
            this.path = changePath = this.rootFolder;
          }
          return this.$emit("change", changePath);
        })
        .catch(console.warn);
    },
    onBlur() {
      this.menuOpen = false;
      this.change(this.path);
    },
    onClear() {
      this.clearFolders(this.orignalPath)
        .then(() => {
          return this.change(this.orginalPath);
        })
        .catch(console.error);
    },
    onKeyDownEnter() {
      this.change(this.path);
    },
    onItemClick(event) {
      this.change(event);
    },
  },
};
</script>

<style scoped lang="scss">
#folderPicker {
  border-radius: 5px;
  background-color: rgb(var(--v-theme-surface));
}
:deep(.showHidden .v-label) {
  color: rgb(var(--v-theme-textSecondary));
}
</style>
