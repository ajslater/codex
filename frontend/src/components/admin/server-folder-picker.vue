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
    :menu-props="{ value: menuOpen }"
    v-bind="$attrs"
    v-on="$listeners"
    @blur="toggleMenu(false)"
    @change="change"
    @click:append="toggleMenu()"
    @focus="clearErrors"
  >
    <template #append-outer>
      <v-tooltip top :open-delay="2000">
        <template #activator="{ on, attrs }">
          <v-icon v-bind="attrs" v-on="on" @click="toggleHidden">
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
  emits: ["change"],
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
  created() {
    this.loadFolders()
      .then(() => {
        this.path = this.rootFolder;
        return true;
      })
      .catch((error) => {
        console.warn(error);
      });
  },
  methods: {
    ...mapActions(useAdminStore, ["loadFolders"]),
    ...mapActions(useCommonStore, ["clearErrors"]),
    change: function (path) {
      const relativePath = !path
        ? this.rootFolder
        : path.startsWith("/")
        ? path
        : [this.rootFolder, path].join("/");
      const isMenuActive = this.$refs.folderPicker.isMenuActive;
      this.clearErrors();
      this.loadFolders(relativePath, this.showHidden)
        .then(() => {
          this.path = this.rootFolder;
          // This keeps the menu scrolling after a menu click.
          this.$refs.folderPicker.isMenuActive = isMenuActive;
          return this.$emit("change", this.path);
        })
        .catch((error) => {
          console.warn(error);
        });
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
