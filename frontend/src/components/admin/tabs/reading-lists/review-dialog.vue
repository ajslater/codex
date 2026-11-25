<template>
  <v-dialog v-model="show" max-width="1100px" scrollable>
    <v-card>
      <v-card-title class="dialogTitle">{{ readingList.name }}</v-card-title>
      <v-card-text>
        <div class="reviewBar">
          <!-- A checklist: nothing ticked is every issue. -->
          <v-chip-group
            v-model="filters"
            class="reviewFilter"
            column
            filter
            multiple
          >
            <v-chip
              v-for="choice of filterChoices"
              :key="choice.value"
              :value="choice.value"
              size="small"
              variant="outlined"
            >
              {{ choice.title }}
            </v-chip>
          </v-chip-group>
          <v-spacer />
          <v-btn
            size="small"
            variant="tonal"
            :disabled="!reviewCount"
            @click="acceptAll"
          >
            Accept All Best Guesses
          </v-btn>
          <span v-if="!reviewCount" class="adminHint reviewHint">
            {{ noReviewHint }}
          </span>
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
            <template v-for="{ key, item, entry } in shownRows" :key="key">
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
                :draggable="!filters.length"
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
                      v-if="!filters.length && entry.liveSource == null"
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
                        :disabled="downTargets.get(entry.pk) === undefined"
                        @click="move(entry, downTargets.get(entry.pk))"
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
                    <v-icon
                      v-if="entry.needsReview"
                      size="small"
                      color="primary"
                    >
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
            <!--
              Rows render a page at a time: a list of thousands built every
              row's controls at once and took seconds to open. Scrolling
              this row into view shows the next page. A function ref, so
              each row v-if creates is watched, after a filter too.
            -->
            <tr v-if="rows.length > shown" :ref="observeRow" class="moreRow">
              <td colspan="7" class="adminNoData">{{ moreCaption }}</td>
            </tr>
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

// Rows rendered at a time, and again each time the end comes into view.
const PAGE_SIZE = 200;
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
});
const FILTER_CHOICES = Object.freeze([
  { value: "review", title: "Needs Review" },
  { value: "missing", title: "Missing" },
  { value: "hidden", title: "Hidden" },
]);

// The ticked filters an opener asks for: "all" ticks none.
function initialFilters(filter) {
  return filter in ENTRY_FILTERS ? [filter] : [];
}

export default {
  name: "ReviewDialog",
  components: { CandidatePicker },
  props: {
    modelValue: { type: Boolean, default: false },
    readingList: { type: Object, required: true },
    initialFilter: { type: String, default: "all" },
    // Admins may save series mappings, which apply to every list.
    admin: { type: Boolean, default: true },
    // Rows rendered at a time. Only tests set it, to page a short list.
    pageSize: { type: Number, default: PAGE_SIZE },
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
      noReviewHint: "No issue needs review.",
      filterChoices: FILTER_CHOICES,
      filters: initialFilters(this.initialFilter),
      allEntries: [],
      // The list's held collections: their issues fold into one row each.
      items: [],
      loading: false,
      loadSeq: 0,
      dragPk: null,
      dragOverPk: null,
      pickEntry: null,
      shown: this.pageSize,
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
      // One fetch of every entry; the ticked filters narrow it here.
      if (!this.filters.length) return this.allEntries;
      const tests = this.filters.map((name) => ENTRY_FILTERS[name]);
      return this.allEntries.filter((entry) =>
        tests.some((test) => test?.(entry)),
      );
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
      if (!this.filters.length) {
        for (const item of this.items) {
          rows.push({
            key: `i${item.pk}`,
            item,
            at: item.position ?? Infinity,
          });
        }
      }
      return rows.sort((a, b) => a.at - b.at);
    },
    downTargets() {
      /*
       * Each entry's position one step down, none when nothing can follow,
       * in one pass: a lookup per row made a long list's render quadratic.
       * The server keeps a collection's block whole, so a step into one
       * goes past it; a list with sources keeps its collections last.
       * One step up needs no help: the server places it before a block.
       */
      const order = this.ordered;
      // The position of the last row of the block each row starts.
      const blockEnd = new Array(order.length);
      for (let index = order.length - 1; index >= 0; index--) {
        const next = order[index + 1];
        blockEnd[index] =
          next && next.liveSource === order[index].liveSource
            ? blockEnd[index + 1]
            : order[index].position;
      }
      const targets = new Map();
      for (let index = 0; index < order.length - 1; index++) {
        const next = order[index + 1];
        let target;
        if (next.liveSource == null) target = next.position;
        else if (!this.isSourced) target = blockEnd[index + 1];
        targets.set(order[index].pk, target);
      }
      return targets;
    },
    shownRows() {
      return this.rows.slice(0, this.shown);
    },
    moreCaption() {
      const total = this.rows.length;
      return `Showing ${this.shown} of ${total}. Scroll for more.`;
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
    filters() {
      this.shown = this.pageSize;
    },
    shown() {
      // The same row, re-watched, so it reports whether it is still in view.
      this.observeMore();
    },
    modelValue(value) {
      if (value) {
        this.filters = initialFilters(this.initialFilter);
        this.load();
      }
    },
    readingList(value, previous) {
      if (value?.pk === previous?.pk) return;
      // Another list: never show the last one's rows while this one loads.
      this.allEntries = [];
      this.items = [];
      this.shown = this.pageSize;
      if (this.modelValue) this.load();
    },
  },
  beforeUnmount() {
    this.moreObserver?.disconnect();
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
        const data = await this.call(API.getEntries(this.readingList.pk));
        // A later load, for another list or after an edit, wins.
        if (seq === this.loadSeq) {
          this.allEntries = data?.entries || [];
          this.items = data?.items || [];
        }
      } finally {
        if (seq === this.loadSeq) this.loading = false;
      }
    },
    showMore() {
      this.shown += this.pageSize;
    },
    observeRow(row) {
      // Vue calls this as the more row mounts (and with null as it goes).
      if (row === this.moreRow) return;
      this.moreRow = row;
      this.observeMore();
    },
    observeMore() {
      // A fresh observer reports at once whether the end is in view.
      this.moreObserver?.disconnect();
      const more = this.moreRow;
      if (!more || typeof IntersectionObserver === "undefined") return;
      this.moreObserver = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) this.showMore();
      });
      this.moreObserver.observe(more);
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
      /*
       * The answer is the entry as it is now: hiding changes no other row
       * here, so the one row is replaced rather than the list refetched.
       */
      const updated = await this.call(
        API.updateEntry(this.readingList.pk, entry.pk, { ignored }),
      );
      if (!updated) return;
      const index = this.allEntries.findIndex((row) => row.pk === updated.pk);
      if (index === -1) {
        await this.load();
      } else {
        this.allEntries.splice(index, 1, updated);
      }
      this.$emit("changed");
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
    flex-wrap: wrap;
    align-items: center;
    gap: $space-2;
    margin-bottom: $space-2;
  }

  .reviewHint {
    margin-top: 0;
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
