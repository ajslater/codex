<template>
  <v-dialog
    :model-value="modelValue"
    max-width="600"
    scrollable
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title> Columns for {{ topGroupLabel }} </v-card-title>
      <v-card-subtitle class="pickerSubtitle">
        Select which columns to show in table view. Settings persist per
        top-group.
      </v-card-subtitle>
      <v-card-text class="pickerBody">
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
      </v-card-text>
      <v-card-actions>
        <v-btn variant="text" @click="resetToDefaults">Reset to Defaults</v-btn>
        <v-spacer />
        <v-btn variant="text" @click="onCancel">Cancel</v-btn>
        <v-btn variant="elevated" color="primary" @click="onSave">Save</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
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
    columns: ["cover", "name", "issue_number", "issue_suffix"],
  },
  {
    label: "Publishing",
    columns: ["publisher_name", "imprint_name", "series_name", "volume_name"],
  },
  {
    label: "Counts",
    columns: ["child_count", "issue_count"],
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
     * Editing state. Snapshotted from the store on dialog open and
     * committed via setSettings() on save; cancel just closes.
     */
    return {
      draft: [],
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
    _snapshot() {
      const stored = this.tableColumns?.[this.topGroup];
      if (Array.isArray(stored) && stored.length > 0) {
        this.draft = [...stored];
      } else {
        this.draft = [...(BROWSER_TABLE_DEFAULT_COLUMNS[this.topGroup] ?? [])];
      }
    },
    toggleColumn(key, on) {
      const set = new Set(this.draft);
      if (on) {
        set.add(key);
      } else {
        set.delete(key);
      }
      /*
       * Preserve the registry's natural order rather than the user's
       * click order — keeps the table visually stable across edits.
       */
      this.draft = Object.keys(BROWSER_TABLE_COLUMNS).filter((k) => set.has(k));
    },
    resetToDefaults() {
      this.draft = [...(BROWSER_TABLE_DEFAULT_COLUMNS[this.topGroup] ?? [])];
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
