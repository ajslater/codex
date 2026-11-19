<template>
  <div class="missingCard" :title="label">
    <div class="missingCover">
      <v-img
        :src="placeholderSrc"
        class="missingCoverImg"
        position="top"
        aria-hidden="true"
      />
      <div class="missingBadge">Missing</div>
      <v-menu v-if="editable" location="bottom end">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            class="missingMenuButton"
            :icon="mdiDotsVertical"
            size="small"
            density="comfortable"
            variant="text"
            :aria-label="`Actions for ${label}`"
          />
        </template>
        <v-list density="compact">
          <v-list-item title="Find the Comic" @click="pickerOpen = true" />
          <v-list-item title="Hide from List" @click="hide" />
        </v-list>
      </v-menu>
    </div>
    <footer class="missingFooter">
      <div class="missingTitle">{{ entry.seriesName || "Unknown series" }}</div>
      <div class="missingSubtitle text-caption">
        <span v-if="entry.issue">#{{ entry.issue }}</span>
        <span v-if="entry.year"> ({{ entry.year }})</span>
        <span v-if="entry.entryType" class="missingType">
          {{ entry.entryType }}
        </span>
      </div>
      <div class="missingPlace text-caption">{{ entry.position + 1 }}</div>
    </footer>
    <CandidatePicker
      v-if="editable"
      v-model="pickerOpen"
      :reading-list-pk="readingListPk"
      :entry="entry"
      @picked="changed"
    />
  </div>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";
import { mapActions } from "pinia";

import { getPlaceholderSrc } from "@/api/v4/browser";
import * as API from "@/api/v4/reading-lists";
import CandidatePicker from "@/components/reading-list-candidate-picker.vue";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

/*
 * A reading list's missing issue, at its place in the grid: the stock
 * cover, its series, issue, year and type. Not a comic, so it is not
 * selectable and opens nothing. A list's editors may find its comic or
 * hide it from the list.
 */
export default {
  name: "MissingCard",
  components: { CandidatePicker },
  props: {
    entry: { type: Object, required: true },
    readingListPk: { type: Number, required: true },
    editable: { type: Boolean, default: false },
  },
  data() {
    return {
      mdiDotsVertical,
      pickerOpen: false,
      placeholderSrc: getPlaceholderSrc("comics"),
    };
  },
  computed: {
    label() {
      const issue = this.entry.issue ? ` #${this.entry.issue}` : "";
      const year = this.entry.year ? ` (${this.entry.year})` : "";
      return `Missing: ${this.entry.seriesName || "Unknown series"}${issue}${year}`;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["refreshBrowserPage"]),
    async changed() {
      this.pickerOpen = false;
      useCommonStore().setNotice("Found the comic for this missing issue.");
      await this.refreshBrowserPage();
    },
    async hide() {
      try {
        await API.updateEntry(this.readingListPk, this.entry.pk, {
          ignored: true,
        });
        useCommonStore().setNotice(
          "Hidden from the list. Show it again in Edit Entries.",
        );
        await this.refreshBrowserPage();
      } catch (error) {
        useCommonStore().setErrorNotice(error);
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/book-cover" as bookcover;

@layer codex-components {
  .missingCard {
    width: bookcover.$cover-width;
  }

  .missingCover {
    position: relative;
    height: bookcover.$cover-height;
    width: bookcover.$cover-width;
    border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 4px;
    overflow: hidden;
  }

  .missingCoverImg {
    height: 100%;
    opacity: 0.35;
    filter: grayscale(1);
  }

  .missingBadge {
    position: absolute;
    bottom: 6px;
    left: 6px;
    padding: 0 6px;
    border-radius: 4px;
    background: rgb(var(--v-theme-surface));
    color: rgb(var(--v-theme-text-secondary));
    font-size: 12px;
  }

  .missingMenuButton {
    position: absolute;
    top: 2px;
    right: 2px;
  }

  .missingFooter {
    color: rgb(var(--v-theme-text-disabled));
    text-align: center;
    padding-top: 4px;
  }

  .missingTitle {
    font-size: 14px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .missingType {
    margin-left: 4px;
    text-transform: capitalize;
  }
}
</style>
