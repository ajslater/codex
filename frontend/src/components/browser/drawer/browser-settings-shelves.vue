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
      @delete="deleteShelf"
    />
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
  methods: {
    ...mapActions(useShelvesStore, [
      "createShelf",
      "deleteShelf",
      "renameShelf",
    ]),
    onRename({ pk, name }) {
      this.renameShelf(pk, name);
    },
    async onCreate(name) {
      this.createError = "";
      const shelf = await this.createShelf(name);
      if (shelf) {
        this.creating = false;
      } else {
        this.createError = "Could not create shelf";
      }
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
</style>
