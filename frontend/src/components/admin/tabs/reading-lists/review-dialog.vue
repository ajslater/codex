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
            :title="reviewCount ? '' : 'No issue needs review.'"
            @click="acceptAll"
          >
            Accept All Best Guesses
          </v-btn>
        </div>
        <p class="adminProse">
          Edits here are saved in Codex only and never change a comic file.
          Dragging a row, moving it with its arrows, or typing its position
          locks the list's order: a refresh then only adds new issues beside
          their neighbours.
        </p>
        <v-progress-linear v-if="loading" indeterminate />
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
            <template v-for="{ key, item, entry } in rows" :key="key">
              <!--
                A held collection is one row: the issues it brings are its,
                so no control here acts on one of them.
              -->
              <tr v-if="item" class="itemRow">
                <td class="positionCol">
                  <v-text-field
                    v-if="!isSourced && item.position != null"
                    :model-value="item.position + 1"
                    inputmode="numeric"
                    density="compact"
                    hide-details
                    variant="plain"
                    class="positionInput"
                    @change="moveItem(item, $event.target.value - 1)"
                  />
                </td>
                <td colspan="5">
                  <span class="itemLabel">{{ item.label }}</span>
                  <span class="itemCount">{{ itemCaption(item) }}</span>
                </td>
                <td class="adminActionCell entryActions">
                  <v-btn
                    v-if="!item.dangling"
                    class="removeItem"
                    :icon="mdiTrashCanOutline"
                    size="small"
                    density="compact"
                    variant="text"
                    title="Remove this collection and its issues"
                    @click="removeItem(item)"
                  />
                </td>
              </tr>
              <tr
                v-else
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
                <div class="positionControls">
                  <!--
                    No number spinner: its up arrow counts the position up,
                    which moves the entry down the list. These arrows move
                    it as they point, one place at a time, so only on the
                    whole list, as dragging.
                  -->
                  <v-text-field
                    :model-value="entry.position + 1"
                    inputmode="numeric"
                    density="compact"
                    hide-details
                    variant="plain"
                    class="positionInput"
                    @change="move(entry, $event.target.value - 1)"
                  />
                  <span
                    v-if="filter === 'all' && entry.liveSource == null"
                    class="moveArrows"
                  >
                    <v-btn
                      class="moveUp"
                      :icon="mdiArrowUp"
                      size="small"
                      density="compact"
                      variant="text"
                      title="Move up"
                      aria-label="Move up"
                      :disabled="entry.position === 0"
                      @click="move(entry, entry.position - 1)"
                    />
                    <v-btn
                      class="moveDown"
                      :icon="mdiArrowDown"
                      size="small"
                      density="compact"
                      variant="text"
                      title="Move down"
                      aria-label="Move down"
                      :disabled="downTarget(entry) === undefined"
                      @click="move(entry, downTarget(entry))"
                    />
                  </span>
                </div>
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
                  :title="entry.ignored ? 'Show in List' : 'Hide from List'"
                  @click="setHidden(entry, !entry.ignored)"
                />
                <v-btn
                  v-if="entry.manual"
                  :icon="mdiTrashCanOutline"
                  size="small"
                  density="compact"
                  variant="text"
                  title="Remove this issue added by hand"
                  @click="remove(entry)"
                />
              </td>
            </tr>
            </template>
            <tr v-if="!rows.length">
              <td colspan="7" class="adminNoData">
                {{ loading ? "Loading…" : "Nothing here." }}
              </td>
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
  mdiArrowDown,
  mdiArrowUp,
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

// The review filters, as the server's entries filters read them.
const ENTRY_FILTERS = Object.freeze({
  review: (entry) => entry.needsReview && !entry.ignored,
  missing: (entry) => !entry.comic && !entry.ignored,
  hidden: (entry) => entry.ignored,
  all: () => true,
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
      mdiArrowDown,
      mdiArrowUp,
      mdiEyeOffOutline,
      mdiEyeOutline,
      mdiHelpCircleOutline,
      mdiMagnify,
      mdiSourceMerge,
      mdiTrashCanOutline,
      filter: this.initialFilter,
      allEntries: [],
      // The list's held collections: their issues fold into one row each.
      items: [],
      loading: false,
      loadSeq: 0,
      dragPk: null,
      dragOverPk: null,
      pickEntry: null,
      pickMapsSeries: false,
      showPicker: false,
    };
  },
  computed: {
    ordered() {
      return [...this.allEntries].sort((a, b) => a.position - b.position);
    },
    isSourced() {
      // A list with document or tags sources keeps its collections last.
      return Boolean(this.readingList?.sources?.length);
    },
    entries() {
      // One fetch of every entry; the filters narrow it here.
      const test = ENTRY_FILTERS[this.filter] || ENTRY_FILTERS.all;
      return this.allEntries.filter((entry) => test(entry));
    },
    rows() {
      /*
       * The table's rows. A held collection is one row at its first issue,
       * and only under All: its issues are never missing, hidden or in
       * need of review.
       */
      const rows = this.entries
        .filter((entry) => entry.liveSource == null)
        .map((entry) => ({ key: `e${entry.pk}`, entry, at: entry.position }));
      if (this.filter === "all") {
        for (const item of this.items) {
          rows.push({ key: `i${item.pk}`, item, at: item.position ?? Infinity });
        }
      }
      return rows.sort((a, b) => a.at - b.at);
    },
    reviewCount() {
      return this.allEntries.filter((entry) => ENTRY_FILTERS.review(entry))
        .length;
    },
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
    modelValue(value) {
      if (value) {
        this.filter = this.initialFilter;
        this.load();
      }
    },
    readingList(value, previous) {
      if (value?.pk === previous?.pk) return;
      // Another list: never show the last one's rows while this one loads.
      this.allEntries = [];
      this.items = [];
      if (this.modelValue) this.load();
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
      const seq = ++this.loadSeq;
      this.loading = true;
      try {
        const data = await this.call(
          API.getEntries(this.readingList.pk, "all"),
        );
        // A later load, for another list or after an edit, wins.
        if (seq === this.loadSeq) {
          this.allEntries = data?.entries || [];
          this.items = data?.items || [];
        }
      } finally {
        if (seq === this.loadSeq) this.loading = false;
      }
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
    itemCaption(item) {
      if (item.dangling) return " — gone from the library";
      const issues = item.count === 1 ? "1 issue" : `${item.count} issues`;
      return ` — ${issues}, kept current`;
    },
    async moveItem(item, position) {
      const target = Math.max(0, Number(position) || 0);
      if (target === item.position) return;
      await this.call(API.reorderItem(this.readingList.pk, item.pk, target));
      await this.changed();
    },
    async removeItem(item) {
      const remove = { [item.collection]: [item.targetId] };
      await this.call(API.updateItems(this.readingList.pk, { remove }));
      await this.changed();
    },
    async remove(entry) {
      await this.call(API.deleteEntry(this.readingList.pk, entry.pk));
      await this.changed();
    },
    downTarget(entry) {
      /*
       * The position one step down, or undefined when nothing can follow.
       * The server keeps a collection's block whole, so a step into one
       * goes past it; a list with sources keeps its collections last.
       * One step up needs no help: the server places it before a block.
       */
      const order = this.ordered;
      const next = order[order.indexOf(entry) + 1];
      if (!next) return;
      if (next.liveSource == null) return next.position;
      if (this.isSourced) return;
      let last = next;
      for (const row of order.slice(order.indexOf(next) + 1)) {
        if (row.liveSource !== next.liveSource) break;
        last = row;
      }
      return last.position;
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
    width: 112px;
  }

  // The number, then the arrows as the Sources dialog's rank arrows sit.
  .positionControls {
    display: flex;
    align-items: center;
  }

  .positionInput {
    width: 48px;
  }

  .moveArrows {
    display: flex;
    white-space: nowrap;
  }

  .entryActions {
    white-space: nowrap;
  }

  .missing,
  .itemCount {
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
