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
          <ShelfMenu :targets="selectedPksByCollection">
            <template #activator="{ props: shelfMenuProps }">
              <v-btn
                v-tooltip="{ text: 'Shelves & Lists', openDelay: 500 }"
                v-bind="shelfMenuProps"
                class="shelvesButton"
                :disabled="!hasSelection"
                density="compact"
                size="small"
                variant="text"
              >
                <v-icon :icon="mdiLibraryShelves" />
                <span class="actionLabel">Shelves &amp; Lists</span>
              </v-btn>
            </template>
          </ShelfMenu>
          <v-btn
            v-if="removeListPk"
            v-tooltip="{ text: 'Remove from List', openDelay: 500 }"
            class="removeFromListButton"
            :disabled="!selectedComicPks.length"
            density="compact"
            size="small"
            variant="text"
            @click="removeSelected"
          >
            <v-icon :icon="mdiPlaylistRemove" />
            <span class="actionLabel">Remove</span>
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
          <v-btn
            v-if="isUserAdmin"
            v-tooltip="{ text: 'Force Update Tags', openDelay: 500 }"
            :disabled="!hasSelection"
            density="compact"
            size="small"
            variant="text"
            @click="onForceUpdateClick"
          >
            <v-icon :icon="mdiAutorenew" />
            <span class="actionLabel">Force Update</span>
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
    <ForceUpdateConfirmDialog
      v-model="showForceUpdateConfirm"
      :affected-count="selectedTotalChildCount"
      :subject="forceUpdateSubject"
      @confirm="forceUpdate"
    />
  </div>
</template>

<script>
import {
  mdiAutorenew,
  mdiBookmarkCheckOutline,
  mdiBookmarkMinusOutline,
  mdiClose,
  mdiDownload,
  mdiLibraryShelves,
  mdiPlaylistRemove,
  mdiTagOutline,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ForceUpdateConfirmDialog from "@/components/force-update-confirm-dialog.vue";
import MetadataDialog from "@/components/metadata/metadata-dialog.vue";
import ShelfMenu from "@/components/shelf-menu.vue";
import { routeReadingListPk } from "@/route";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useBrowserSelectManyStore } from "@/stores/browser-select-many";
import { useReadingListsStore } from "@/stores/reading-lists";

const CHILD_WARNING_LIMIT = 99;

export default {
  name: "BrowserSelectManyToolbar",
  components: {
    ForceUpdateConfirmDialog,
    MetadataDialog,
    ShelfMenu,
  },
  data() {
    return {
      mdiAutorenew,
      mdiBookmarkCheckOutline,
      mdiBookmarkMinusOutline,
      mdiClose,
      mdiDownload,
      mdiLibraryShelves,
      mdiPlaylistRemove,
      mdiTagOutline,
      showMetadataDialog: false,
      showForceUpdateConfirm: false,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    ...mapState(useBrowserSelectManyStore, [
      "active",
      "selectedCount",
      "selectedTotalChildCount",
      "hasSelection",
      "compositeItem",
      "selectedPksByCollection",
    ]),
    ...mapState(useBrowserStore, {
      listEditable: (state) => Boolean(state.page.listEditable),
    }),
    removeListPk() {
      // Inside a reading list this user may change: remove in place.
      if (!this.listEditable) return 0;
      return routeReadingListPk(this.$route?.params);
    },
    selectedComicPks() {
      return this.selectedPksByCollection?.comics || [];
    },
    forceUpdateSubject() {
      const itemNoun = this.selectedCount === 1 ? "item" : "items";
      return `across ${this.selectedCount} selected ${itemNoun}`;
    },
  },
  methods: {
    ...mapActions(useBrowserSelectManyStore, [
      "clearSelection",
      "markFinished",
      "download",
      "forceUpdate",
    ]),
    ...mapActions(useBrowserStore, ["refreshBrowserPage"]),
    ...mapActions(useReadingListsStore, ["removeFromList"]),
    async removeSelected() {
      const comics = this.selectedComicPks;
      if (!comics.length) return;
      if (await this.removeFromList(this.removeListPk, comics)) {
        this.clearSelection();
        await this.refreshBrowserPage();
      }
    },
    openTags() {
      if (this.compositeItem) {
        this.showMetadataDialog = true;
      }
    },
    onForceUpdateClick() {
      if (!this.hasSelection) {
        return;
      }
      if (this.selectedTotalChildCount > CHILD_WARNING_LIMIT) {
        this.showForceUpdateConfirm = true;
      } else {
        this.forceUpdate();
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
  color: rgb(var(--v-theme-text-secondary));
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
    border: thin solid rgb(var(--v-theme-text-disabled));
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
