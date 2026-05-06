<template>
  <v-dialog
    :model-value="modelValue"
    max-width="640"
    scrollable
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title> Columns for {{ topGroupLabel }} </v-card-title>
      <v-card-subtitle class="pickerSubtitle">
        Drag columns in the Order list to rearrange them. Toggle a column in the
        Add list to show or hide it.
      </v-card-subtitle>
      <v-card-text class="pickerBody">
        <section class="orderSection">
          <div class="sectionHeader">Order ({{ draft.length }})</div>
          <ol v-if="draft.length > 0" class="orderList">
            <li
              v-for="(col, index) in draft"
              :key="col"
              class="orderItem"
              :class="{
                dragging: draggingIndex === index,
                dropAbove: dropOverIndex === index && dropOverPos === 'above',
                dropBelow: dropOverIndex === index && dropOverPos === 'below',
              }"
              draggable="true"
              @dragstart="onDragStart(index, $event)"
              @dragover.prevent="onDragOver(index, $event)"
              @dragleave="onDragLeave(index)"
              @drop.prevent="onDrop(index)"
              @dragend="onDragEnd"
            >
              <v-icon class="dragHandle" :icon="mdiDragVertical" size="20" />
              <span class="orderItemLabel">{{ labelFor(col) }}</span>
              <v-btn
                :icon="mdiClose"
                size="x-small"
                variant="text"
                density="compact"
                :aria-label="`remove ${labelFor(col)}`"
                @click="removeColumn(col)"
              />
            </li>
          </ol>
          <div v-else class="orderEmpty">No columns selected.</div>
        </section>
        <section class="categoriesSection">
          <div class="sectionHeader">Add Columns</div>
          <div
            v-for="category in categoriesWithColumns"
            :key="category.label"
            class="pickerCategory"
          >
            <div class="pickerCategoryHeader">{{ category.label }}</div>
            <v-checkbox
              v-for="col in category.columns"
              :key="col.key"
              :model-value="selectedSet.has(col.key)"
              :label="col.label"
              density="compact"
              hide-details
              @update:model-value="toggleColumn(col.key, $event)"
            />
          </div>
        </section>
      </v-card-text>
      <v-card-actions class="pickerActions">
        <v-btn variant="text" @click="selectAll">All</v-btn>
        <v-btn variant="text" @click="selectNone">None</v-btn>
        <v-btn variant="text" @click="resetToDefaults">Defaults</v-btn>
        <v-spacer />
        <v-btn variant="text" @click="onCancel">Cancel</v-btn>
        <v-btn variant="elevated" color="primary" @click="onSave">Save</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mdiClose, mdiDragVertical } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import BROWSER_TABLE_COLUMNS from "@/choices/browser-table-columns.json";
import BROWSER_TABLE_DEFAULT_COLUMNS from "@/choices/browser-table-default-columns.json";
import { TOP_GROUP } from "@/choices/browser-map.json";
import { useBrowserStore } from "@/stores/browser";

/*
 * Hardcoded category groupings. The registry doesn't carry a category
 * field — we hardcode here for v1 since the categories are stable and
 * there's no use case yet for letting them be configured from the
 * backend. Columns not listed in any category are appended to "Other".
 */
const _CATEGORIES = Object.freeze([
  {
    label: "Identity",
    columns: ["cover", "name", "issue"],
  },
  {
    label: "Publishing",
    columns: ["publisher_name", "imprint_name", "series_name", "volume_name"],
  },
  {
    label: "Counts",
    columns: ["child_count"],
  },
  {
    label: "Files",
    columns: ["file_name", "size", "page_count", "file_type"],
  },
  {
    label: "Dates",
    columns: [
      "year",
      "month",
      "day",
      "date",
      "created_at",
      "updated_at",
      "metadata_mtime",
      "bookmark_updated_at",
    ],
  },
  {
    label: "Tagging",
    columns: [
      "country",
      "language",
      "original_format",
      "tagger",
      "scan_info",
      "age_rating",
      "main_character",
      "main_team",
    ],
  },
  {
    label: "Reader",
    columns: ["reading_direction", "monochrome", "critical_rating"],
  },
  {
    label: "Tags & People",
    columns: [
      "characters",
      "credits",
      "genres",
      "identifiers",
      "locations",
      "series_groups",
      "stories",
      "story_arcs",
      "tags",
      "teams",
      "universes",
    ],
  },
]);

function _registryEntry(key) {
  return Object.hasOwn(BROWSER_TABLE_COLUMNS, key)
    ? // eslint-disable-next-line security/detect-object-injection
      BROWSER_TABLE_COLUMNS[key]
    : undefined;
}

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "BrowserTableColumnPicker",
  props: {
    modelValue: {
      type: Boolean,
      required: true,
    },
  },
  emits: ["update:modelValue"],
  data() {
    /*
     * Editing state. ``draft`` is the user's draft column order;
     * ``draggingIndex`` and ``dropOverIndex`` track the in-flight
     * drag for visual feedback. Snapshotted on dialog open and
     * committed via setSettings() on save.
     */
    return {
      mdiClose,
      mdiDragVertical,
      draft: [],
      draggingIndex: null,
      dropOverIndex: null,
      dropOverPos: null,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      topGroup: (state) => state.settings.topGroup,
      tableColumns: (state) => state.settings.tableColumns,
    }),
    topGroupLabel() {
      return TOP_GROUP[this.topGroup] ?? this.topGroup;
    },
    selectedSet() {
      return new Set(this.draft);
    },
    categoriesWithColumns() {
      const seen = new Set();
      const categories = _CATEGORIES
        .map((cat) => {
          const columns = [];
          for (const key of cat.columns) {
            const entry = _registryEntry(key);
            if (!entry) continue;
            seen.add(key);
            columns.push({ key, label: entry.label });
          }
          return { label: cat.label, columns };
        })
        .filter((c) => c.columns.length > 0);
      /*
       * Surface anything in the registry that wasn't categorized so
       * future additions don't silently disappear from the picker.
       */
      const orphans = [];
      for (const key of Object.keys(BROWSER_TABLE_COLUMNS)) {
        if (seen.has(key)) continue;
        const entry = _registryEntry(key);
        if (!entry) continue;
        orphans.push({ key, label: entry.label });
      }
      if (orphans.length > 0) {
        categories.push({ label: "Other", columns: orphans });
      }
      return categories;
    },
  },
  watch: {
    modelValue(open) {
      if (open) this._snapshot();
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    labelFor(key) {
      return _registryEntry(key)?.label ?? key;
    },
    _snapshot() {
      const stored = this.tableColumns?.[this.topGroup];
      if (Array.isArray(stored) && stored.length > 0) {
        this.draft = [...stored];
      } else {
        this.draft = [...(BROWSER_TABLE_DEFAULT_COLUMNS[this.topGroup] ?? [])];
      }
    },
    toggleColumn(key, on) {
      if (on) {
        if (!this.draft.includes(key)) {
          /*
           * New columns are appended to the end of the order list.
           * The user can drag them into position from there.
           */
          this.draft = [...this.draft, key];
        }
      } else {
        this.draft = this.draft.filter((k) => k !== key);
      }
    },
    removeColumn(key) {
      this.draft = this.draft.filter((k) => k !== key);
    },
    resetToDefaults() {
      this.draft = [...(BROWSER_TABLE_DEFAULT_COLUMNS[this.topGroup] ?? [])];
    },
    selectAll() {
      this.draft = Object.keys(BROWSER_TABLE_COLUMNS);
    },
    selectNone() {
      this.draft = [];
    },
    /*
     * Drag-and-drop reordering. HTML5 native API — no extra dep.
     * The pointer's position relative to the row's vertical midpoint
     * decides whether the drop target is "above" or "below"; that
     * controls the visual indicator and the final insertion index.
     */
    onDragStart(index, event) {
      this.draggingIndex = index;
      // ``move`` shows the drag-and-move cursor.
      event.dataTransfer.effectAllowed = "move";
      // Setting any data is required for Firefox to actually drag.
      event.dataTransfer.setData("text/plain", String(index));
    },
    onDragOver(index, event) {
      if (this.draggingIndex === null) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const midpoint = rect.top + rect.height / 2;
      this.dropOverIndex = index;
      this.dropOverPos = event.clientY < midpoint ? "above" : "below";
      event.dataTransfer.dropEffect = "move";
    },
    onDragLeave(index) {
      if (this.dropOverIndex === index) {
        this.dropOverIndex = null;
        this.dropOverPos = null;
      }
    },
    onDrop(index) {
      const from = this.draggingIndex;
      const pos = this.dropOverPos;
      this.draggingIndex = null;
      this.dropOverIndex = null;
      this.dropOverPos = null;
      if (from === null || from === index) return;
      let to = pos === "below" ? index + 1 : index;
      // After splicing out ``from``, indexes ≥ from shift down by one.
      if (from < to) to -= 1;
      if (from === to) return;
      const next = [...this.draft];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      this.draft = next;
    },
    onDragEnd() {
      this.draggingIndex = null;
      this.dropOverIndex = null;
      this.dropOverPos = null;
    },
    onCancel() {
      this.$emit("update:modelValue", false);
    },
    onSave() {
      const next = {
        ...(this.tableColumns ?? {}),
        [this.topGroup]: this.draft,
      };
      this.setSettings({ tableColumns: next });
      this.$emit("update:modelValue", false);
    },
  },
};
</script>

<style scoped lang="scss">
.pickerSubtitle {
  white-space: normal;
  padding-bottom: 12px;
}

.pickerBody {
  max-height: 60vh;
  overflow-y: auto;
}

.sectionHeader {
  font-size: 0.85em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgb(var(--v-theme-textSecondary));
  margin: 8px 0 6px;
}

.orderSection {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.orderList {
  list-style: none;
  padding: 0;
  margin: 0;
}

.orderItem {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 4px;
  background-color: rgb(var(--v-theme-surface-light));
  margin-bottom: 4px;
  cursor: grab;
  user-select: none;
  /* Drop indicators: the inset shadow draws a 2px line above or below
     the hovered row to show where the dragged item will land. */
  border-top: 2px solid transparent;
  border-bottom: 2px solid transparent;
}

.orderItem:active {
  cursor: grabbing;
}

.orderItem.dragging {
  opacity: 0.4;
}

.orderItem.dropAbove {
  border-top-color: rgb(var(--v-theme-primary));
}

.orderItem.dropBelow {
  border-bottom-color: rgb(var(--v-theme-primary));
}

.dragHandle {
  cursor: grab;
  opacity: 0.6;
}

.orderItemLabel {
  flex: 1;
}

.orderEmpty {
  color: rgb(var(--v-theme-textDisabled));
  font-size: 0.9em;
  padding: 4px 8px;
}

.pickerCategory + .pickerCategory {
  margin-top: 12px;
}

.pickerCategoryHeader {
  font-size: 0.85em;
  font-weight: 600;
  text-transform: uppercase;
  color: rgb(var(--v-theme-textSecondary));
  margin-bottom: 4px;
}
</style>
