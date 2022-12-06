<template>
  <v-combobox
    ref="folderPicker"
    v-model="path"
    auto-select-first
    filled
    class="folderPicker"
    :append-icon="mdiFileTree"
    :items="folders"
    :error-messages="formErrors"
    :menu-props="{ value: menuOpen, maxHeight: '75%' }"
    v-bind="$attrs"
    @blur="toggleMenu(false)"
    @update:modelValue="change"
    @click:append="toggleMenu()"
    @focus="clearErrors"
  >
    <template #append-outer>
      <v-tooltip top :open-delay="2000">
        <template #activator="{ props }">
          <v-icon v-bind="props" @click="toggleHidden">
            {{ appendOuterIcon }}
          </v-icon>
        </template>
        <span>{{ showHiddenTooltipPrefix }} Hidden Folders</span>
      </v-tooltip>
    </template>
  </v-combobox>
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
      const isMenuActive = this.$refs.folderPicker.isMenuActive;
      this.clearErrors();
      this.loadFolders(relativePath, this.showHidden)
        .then(() => {
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
  },
};
</script>

<style scoped lang="scss">
.showHidden {
  margin-right: auto;
}
</style>
