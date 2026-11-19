<template>
  <v-dialog v-model="show" max-width="1100px" scrollable>
    <v-card>
      <v-card-title class="dialogTitle">{{ readingList.name }}</v-card-title>
      <v-card-text>
        <div class="reviewBar">
          <v-btn-toggle
            v-model="filter"
            density="compact"
            mandatory
            variant="outlined"
          >
            <v-btn value="review">Needs Review</v-btn>
            <v-btn value="missing">Missing</v-btn>
            <v-btn value="all">All</v-btn>
            <v-btn value="hidden">Hidden</v-btn>
          </v-btn-toggle>
          <v-spacer />
          <v-btn
            size="small"
            variant="tonal"
            :disabled="!reviewCount"
            :title="reviewCount ? '' : 'No entry needs review.'"
            @click="acceptAll"
          >
            Accept All Best Guesses
          </v-btn>
        </div>
        <p class="adminProse">
          Edits here are saved in Codex only and never change a comic file.
          Dragging a row, or typing its position, locks the list's order: a
          refresh then only adds new entries beside their neighbours.
        </p>
        <v-table density="compact" class="entriesTable">
          <thead>
            <tr>
              <th class="positionCol">#</th>
              <th>Series</th>
              <th>Issue</th>
              <th>Year</th>
              <th>Type</th>
              <th>Comic</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in entries"
              :key="entry.pk"
              :class="{
                dragOver: dragOverPk === entry.pk,
                hidden: entry.ignored,
              }"
              :draggable="filter === 'all'"
              @dragstart="dragStart(entry)"
              @dragover.prevent="dragOverPk = entry.pk"
              @dragleave="dragOverPk = null"
              @drop.prevent="drop(entry)"
            >
              <td class="positionCol">
                <v-text-field
                  :model-value="entry.position + 1"
                  type="number"
                  min="1"
                  density="compact"
                  hide-details
                  variant="plain"
                  class="positionInput"
                  @change="move(entry, $event.target.value - 1)"
                />
              </td>
              <td>{{ entry.seriesName }}</td>
              <td>{{ entry.issue }}</td>
              <td>{{ entry.year }}</td>
              <td>{{ entry.entryType }}</td>
              <td>
                <span v-if="entry.comic" :title="tierTitle(entry)">
                  {{ comicLabel(entry.comic) }}
                  <v-icon v-if="entry.needsReview" size="small" color="primary">
                    {{ mdiHelpCircleOutline }}
                  </v-icon>
                </span>
                <span v-else class="missing">{{ missingLabel(entry) }}</span>
              </td>
              <td class="adminActionCell entryActions">
                <v-btn
                  :icon="mdiMagnify"
                  size="small"
                  density="compact"
                  variant="text"
                  title="Find the comic"
                  @click="find(entry)"
                />
                <v-btn
                  v-if="admin && entry.seriesName"
                  :icon="mdiSourceMerge"
                  size="small"
                  density="compact"
                  variant="text"
                  title="Map this series to a library series, for every row and list"
                  @click="find(entry, true)"
                />
                <v-btn
                  :icon="entry.ignored ? mdiEyeOutline : mdiEyeOffOutline"
                  size="small"
                  density="compact"
                  variant="text"
                  :title="entry.ignored ? 'Show' : 'Hide from the list'"
                  @click="setHidden(entry, !entry.ignored)"
                />
                <v-btn
                  v-if="entry.manual"
                  :icon="mdiTrashCanOutline"
                  size="small"
                  density="compact"
                  variant="text"
                  title="Remove this hand-added entry"
                  @click="remove(entry)"
                />
              </td>
            </tr>
            <tr v-if="!entries.length">
              <td colspan="7" class="adminNoData">Nothing here.</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="show = false">Close</v-btn>
      </v-card-actions>
    </v-card>
    <CandidatePicker
      v-if="pickEntry"
      v-model="showPicker"
      :reading-list-pk="readingList.pk"
      :entry="pickEntry"
      :map-series="pickMapsSeries"
      @picked="picked"
    />
  </v-dialog>
</template>

<script>
import {
  mdiEyeOffOutline,
  mdiEyeOutline,
  mdiHelpCircleOutline,
  mdiMagnify,
  mdiSourceMerge,
  mdiTrashCanOutline,
} from "@mdi/js";

import * as API from "@/api/v4/reading-lists";
import CandidatePicker from "@/components/reading-list-candidate-picker.vue";
import { useCommonStore } from "@/stores/common";

const TIERS = Object.freeze({
  marked_missing: "Marked missing by hand",
  manual: "Picked by hand",
  tagged: "Its own story arc tag",
  mapping: "A saved series mapping",
  issue_id: "An issue id",
  series_id: "The series id and number",
  exact_name: "The series name and number",
  normalized_name: "A variant of the series name",
});

export default {
  name: "ReviewDialog",
  components: { CandidatePicker },
  props: {
    modelValue: { type: Boolean, default: false },
    readingList: { type: Object, required: true },
    initialFilter: { type: String, default: "all" },
    // Admins may save series mappings, which apply to every list.
    admin: { type: Boolean, default: true },
  },
  emits: ["update:modelValue", "changed"],
  data() {
    return {
      mdiEyeOffOutline,
      mdiEyeOutline,
      mdiHelpCircleOutline,
      mdiMagnify,
      mdiSourceMerge,
      mdiTrashCanOutline,
      filter: this.initialFilter,
      entries: [],
      reviewCount: 0,
      dragPk: null,
      dragOverPk: null,
      pickEntry: null,
      pickMapsSeries: false,
      showPicker: false,
    };
  },
  computed: {
    show: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit("update:modelValue", value);
      },
    },
  },
  watch: {
    filter() {
      this.load();
    },
    modelValue(value) {
      if (value) {
        this.filter = this.initialFilter;
        this.load();
      }
    },
  },
  mounted() {
    if (this.modelValue) this.load();
  },
  methods: {
    async call(promise) {
      try {
        const response = await promise;
        return response.data;
      } catch (error) {
        useCommonStore().setErrorNotice(error);
      }
    },
    async load() {
      const data = await this.call(
        API.getEntries(this.readingList.pk, this.filter),
      );
      this.entries = data?.entries || [];
      const review = await this.call(
        API.getEntries(this.readingList.pk, "review"),
      );
      this.reviewCount = review?.entries?.length || 0;
    },
    async changed() {
      await this.load();
      this.$emit("changed");
    },
    comicLabel(comic) {
      const volume = comic.volumeName ? ` ${comic.volumeName}` : "";
      // A year-like volume already says the year.
      const year =
        comic.year && comic.volumeName !== `(${comic.year})`
          ? ` (${comic.year})`
          : "";
      return `${comic.seriesName}${volume} #${comic.issue}${year}`;
    },
    missingLabel(entry) {
      return entry.matchTier === "marked_missing"
        ? "Marked missing"
        : "Missing";
    },
    tierTitle(entry) {
      const tier = TIERS[entry.matchTier] || "Matched";
      return entry.needsReview
        ? `${tier}; check it: several could be it`
        : tier;
    },
    async setHidden(entry, ignored) {
      await this.call(
        API.updateEntry(this.readingList.pk, entry.pk, { ignored }),
      );
      await this.changed();
    },
    async remove(entry) {
      await this.call(API.deleteEntry(this.readingList.pk, entry.pk));
      await this.changed();
    },
    async move(entry, position) {
      const target = Math.max(0, Number(position) || 0);
      if (target === entry.position) return;
      await this.call(API.reorderEntry(this.readingList.pk, entry.pk, target));
      await this.changed();
    },
    dragStart(entry) {
      this.dragPk = entry.pk;
    },
    async drop(entry) {
      this.dragOverPk = null;
      const dragged = this.entries.find((row) => row.pk === this.dragPk);
      this.dragPk = null;
      if (dragged && dragged.pk !== entry.pk) {
        await this.move(dragged, entry.position);
      }
    },
    async acceptAll() {
      await this.call(API.acceptEntries(this.readingList.pk));
      await this.changed();
    },
    find(entry, mapSeries = false) {
      this.pickEntry = entry;
      this.pickMapsSeries = mapSeries;
      this.showPicker = true;
    },
    async picked() {
      this.showPicker = false;
      await this.changed();
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as *;

@layer codex-components {
  .reviewBar {
    display: flex;
    align-items: center;
    gap: $space-2;
    margin-bottom: $space-2;
  }

  .positionCol {
    width: 72px;
  }

  .positionInput {
    width: 64px;
  }

  .entryActions {
    white-space: nowrap;
  }

  .missing {
    color: rgb(var(--v-theme-text-disabled));
  }

  .hidden {
    opacity: 0.5;
  }

  .dragOver {
    background-color: rgba(var(--v-theme-primary), 0.15);
  }

  .dialogTitle {
    font-weight: bold;
  }
}
</style>
