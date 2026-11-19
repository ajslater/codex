<template>
  <div v-if="isLoggedIn" class="shelvesSettingsBlock">
    <div class="settingsSubHeader">Shelves</div>
    <NameListEditor
      :items="shelfItems"
      noun="shelf"
      empty-text="No shelves yet"
      delete-hint="Nothing on it is deleted."
      :max-length="maxLength"
      @rename="onRename"
      @delete="onDelete"
    />
    <p v-if="shelfError" class="shelvesSettingsError">{{ shelfError }}</p>
    <ShelfNameInput
      v-if="creating"
      class="shelvesSettingsNameInput"
      :error="createError"
      :existing-names="shelfNames"
      @cancel="creating = false"
      @submit="onCreate"
    />
    <v-btn
      v-else
      class="shelvesSettingsNewBtn"
      density="compact"
      :prepend-icon="mdiPlus"
      size="small"
      variant="text"
      @click="creating = true"
    >
      New shelf
    </v-btn>
  </div>
  <v-divider v-if="isLoggedIn" />
</template>

<script>
import { mdiPlus } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import NameListEditor from "@/components/name-list-editor.vue";
import ShelfNameInput, {
  SHELF_NAME_MAX_LENGTH,
} from "@/components/shelf-name-input.vue";
import { useAuthStore } from "@/stores/auth";
import { getErrors } from "@/stores/common";
import { useShelvesStore } from "@/stores/shelves";

export default {
  name: "BrowserSettingsShelves",
  components: { NameListEditor, ShelfNameInput },
  data() {
    return {
      createError: "",
      creating: false,
      maxLength: SHELF_NAME_MAX_LENGTH,
      mdiPlus,
      // Why the last rename or delete failed.
      shelfError: "",
    };
  },
  computed: {
    ...mapState(useAuthStore, {
      isLoggedIn: (state) => Boolean(state.user),
    }),
    ...mapState(useShelvesStore, ["itemCount", "shelfNames", "shelves"]),
    shelfItems() {
      return this.shelves.map((shelf) => ({
        pk: shelf.pk,
        name: shelf.name,
        count: this.itemCount(shelf),
      }));
    },
  },
  watch: {
    creating() {
      // Opening or closing the name input drops the last attempt's error.
      this.createError = "";
    },
  },
  methods: {
    ...mapActions(useShelvesStore, [
      "createShelf",
      "deleteShelf",
      "renameShelf",
    ]),
    shelfName(pk) {
      return this.shelves.find((shelf) => shelf.pk === pk)?.name ?? "";
    },
    async onRename({ pk, name }) {
      const oldName = this.shelfName(pk);
      this.shelfError = "";
      if (!(await this.renameShelf(pk, name))) {
        this.shelfError = `Could not rename the shelf "${oldName}".`;
      }
    },
    async onDelete(pk) {
      const name = this.shelfName(pk);
      this.shelfError = "";
      if (!(await this.deleteShelf(pk))) {
        this.shelfError = `Could not delete the shelf "${name}".`;
      }
    },
    async onCreate(name) {
      this.createError = "";
      try {
        await this.createShelf(name);
      } catch (error) {
        this.createError = getErrors(error).join(" ");
        return;
      }
      this.creating = false;
    },
  },
};
</script>

<style scoped lang="scss">
// settingsSubHeader defined in styles/global.scss
.shelvesSettingsBlock {
  padding-bottom: 5px;
}

.shelvesSettingsNameInput {
  padding: 5px 10px;
}

.shelvesSettingsNewBtn {
  margin-left: 10px;
}

.shelvesSettingsError {
  padding: 0 15px 5px;
  color: rgb(var(--v-theme-error));
}
</style>
