<template>
  <div>
    <v-slide-y-transition>
      <v-toolbar
        v-if="active"
        id="selectManyToolbar"
        density="compact"
        :height="40"
      >
        <span class="selectManyCount">
          {{ selectedCount }}
          <span class="selectManyCountLabel">
            {{ selectedCount === 1 ? "item" : "items" }} selected
          </span>
        </span>
        <v-spacer />
        <div class="actionButtons">
          <v-btn
            v-tooltip="{ text: 'Tags', openDelay: 500 }"
            :disabled="!hasSelection"
            density="compact"
            size="small"
            variant="text"
            @click="openTags"
          >
            <v-icon :icon="mdiTagOutline" />
            <span class="actionLabel">Tags</span>
          </v-btn>
          <v-btn
            v-tooltip="{ text: 'Mark Read', openDelay: 500 }"
            :disabled="!hasSelection"
            density="compact"
            size="small"
            variant="text"
            @click="markFinished(true)"
          >
            <v-icon :icon="mdiBookmarkCheckOutline" />
            <span class="actionLabel">Read</span>
          </v-btn>
          <v-btn
            v-tooltip="{ text: 'Mark Unread', openDelay: 500 }"
            :disabled="!hasSelection"
            density="compact"
            size="small"
            variant="text"
            @click="markFinished(false)"
          >
            <v-icon :icon="mdiBookmarkMinusOutline" />
            <span class="actionLabel">Unread</span>
          </v-btn>
          <v-btn
            v-tooltip="{ text: 'Download', openDelay: 500 }"
            :disabled="!hasSelection"
            density="compact"
            size="small"
            variant="text"
            @click="download"
          >
            <v-icon :icon="mdiDownload" />
            <span class="actionLabel">Download</span>
          </v-btn>
        </div>
        <v-spacer />
        <v-btn
          density="compact"
          size="small"
          variant="text"
          @click="clearSelection"
        >
          <span class="deselectLabel">Deselect All</span>
          <v-icon :icon="mdiClose" />
        </v-btn>
      </v-toolbar>
    </v-slide-y-transition>
    <MetadataDialog
      v-if="showMetadataDialog"
      :book="compositeItem"
      no-activator
      @close="showMetadataDialog = false"
    />
  </div>
</template>

<script>
import {
  mdiBookmarkCheckOutline,
  mdiBookmarkMinusOutline,
  mdiClose,
  mdiDownload,
  mdiTagOutline,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";

import MetadataDialog from "@/components/metadata/metadata-dialog.vue";
import { useSelectManyStore } from "@/stores/select-many";

export default {
  name: "BrowserSelectManyToolbar",
  components: {
    MetadataDialog,
  },
  data() {
    return {
      mdiBookmarkCheckOutline,
      mdiBookmarkMinusOutline,
      mdiClose,
      mdiDownload,
      mdiTagOutline,
      showMetadataDialog: false,
    };
  },
  computed: {
    ...mapState(useSelectManyStore, [
      "active",
      "selectedCount",
      "hasSelection",
      "compositeItem",
    ]),
  },
  methods: {
    ...mapActions(useSelectManyStore, [
      "clearSelection",
      "markFinished",
      "download",
    ]),
    openTags() {
      if (this.compositeItem) {
        this.showMetadataDialog = true;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

#selectManyToolbar {
  padding-left: max(18px, calc(env(safe-area-inset-left) / 2));
  padding-right: max(10px, calc(env(safe-area-inset-right) / 2));
  border-radius: 4px;
}

.selectManyCount {
  font-size: 13px;
  color: rgb(var(--v-theme-textSecondary));
  white-space: nowrap;
  padding-left: 8px;
}

.selectManyCountLabel {
  padding-left: 4px;
  display: inline-block;
  min-width: 8em;
}

.actionButtons {
  display: flex;
  align-items: center;
}

.actionLabel {
  padding-left: 4px;
}

.deselectLabel {
  padding-right: 4px;
}

@media #{map.get(vuetify.$display-breakpoints, 'xs')} {
  .selectManyCountLabel {
    display: none;
  }

  .actionLabel {
    display: none;
  }

  .deselectLabel {
    display: none;
  }

  .actionButtons {
    gap: 8px;
    border: thin solid rgb(var(--v-theme-textDisabled));
    border-radius: 4px;
    padding: 2px 6px;
  }
}

@media #{map.get(vuetify.$display-breakpoints, 'sm')} {
  .actionLabel {
    display: none;
  }

  .actionButtons {
    gap: 8px;
  }
}
</style>
