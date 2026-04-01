<template>
  <div class="savedSettingsBlock">
    <div class="settingsSubHeader">Saved Views</div>
    <div class="savedSettingsRow">
      <v-combobox
        v-model="selectedName"
        :items="savedItems"
        class="savedSettingsCombobox"
        clearable
        density="compact"
        hide-details="auto"
        item-title="name"
        item-value="name"
        label="Load Saved View"
        :menu-props="{ maxHeight: 300 }"
        return-object
        variant="outlined"
        @update:model-value="onSelect"
        @click:clear="onClear"
      />
      <v-btn
        class="savedSettingsSaveBtn"
        density="compact"
        :icon="mdiContentSave"
        size="small"
        title="Save Current View"
        @click="showSaveDialog = true"
      />
    </div>
  </div>
  <!-- Save dialog -->
  <v-dialog
    v-model="showSaveDialog"
    min-width="20em"
    width="auto"
    transition="fab-transition"
  >
    <div class="saveDialog">
      <div class="saveDialogTitle">Save View</div>
      <v-text-field
        v-model="saveName"
        autofocus
        density="compact"
        hide-details="auto"
        label="View Name"
        variant="outlined"
        @keyup.enter="onSaveSubmit"
      />
      <div class="saveDialogActions">
        <v-btn size="small" @click="showSaveDialog = false">Cancel</v-btn>
        <v-btn
          color="primary"
          :disabled="!saveName"
          size="small"
          @click="onSaveSubmit"
        >
          Save
        </v-btn>
      </div>
    </div>
  </v-dialog>
  <!-- Overwrite confirmation dialog -->
  <v-dialog
    v-model="showOverwriteConfirm"
    min-width="20em"
    width="auto"
    transition="fab-transition"
  >
    <div class="saveDialog">
      <div class="saveDialogTitle">Overwrite View</div>
      <div>
        A saved view named "<strong>{{ saveName }}</strong
        >" already exists. Overwrite it?
      </div>
      <div class="saveDialogActions">
        <v-btn size="small" @click="showOverwriteConfirm = false">
          Cancel
        </v-btn>
        <v-btn color="warning" size="small" @click="doSave">Overwrite</v-btn>
      </div>
    </div>
  </v-dialog>
  <v-divider />
</template>
<script>
import { mdiContentSave } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserSettingsSaved",
  data() {
    return {
      mdiContentSave,
      selectedName: null,
      showSaveDialog: false,
      showOverwriteConfirm: false,
      saveName: "",
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      savedItems: (state) => state.savedSettingsList || [],
      browserSettings: (state) => state.settings,
    }),
    existingNames() {
      return new Set(this.savedItems.map((item) => item.name));
    },
  },
  watch: {
    browserSettings: {
      handler() {
        this.selectedName = null;
      },
      deep: true,
    },
  },
  created() {
    this.loadSavedSettingsList();
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "loadSavedSettingsList",
      "saveCurrentSettings",
      "loadSavedSettings",
    ]),
    onSelect(item) {
      if (!item) {
        return;
      }
      if (typeof item === "object" && item.pk != null) {
        this.loadSavedSettings(item.pk);
      }
    },
    onClear() {
      this.selectedName = null;
    },
    onSaveSubmit() {
      if (!this.saveName) {
        return;
      }
      if (this.existingNames.has(this.saveName)) {
        this.showSaveDialog = false;
        this.showOverwriteConfirm = true;
      } else {
        this.doSave();
      }
    },
    doSave() {
      this.showSaveDialog = false;
      this.showOverwriteConfirm = false;
      this.saveCurrentSettings(this.saveName);
      this.saveName = "";
    },
  },
};
</script>
<style scoped lang="scss">
.savedSettingsBlock {
  padding-bottom: 5px;
}

.savedSettingsRow {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 5px;
  padding-left: 10px;
  padding-right: 10px;
}

.savedSettingsCombobox {
  flex: 1;
}

.savedSettingsSaveBtn {
  flex-shrink: 0;
}

.saveDialog {
  padding: 20px;
  text-align: center;
}

.saveDialogTitle {
  padding-bottom: 10px;
  font-weight: bolder;
  font-size: larger;
}

.saveDialogActions {
  display: flex;
  justify-content: center;
  gap: 10px;
  padding-top: 15px;
}
</style>
