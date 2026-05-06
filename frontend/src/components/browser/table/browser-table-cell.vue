<template>
  <span
    v-if="column === 'cover'"
    class="tableCoverCell"
    :class="coverSizeClass"
  >
    <img
      :src="imgSrc"
      :alt="row.name || ''"
      :title="row.name || ''"
      @error="onImgError"
    />
  </span>
  <span v-else-if="isList" class="tableListCell" :title="listValue">{{
    listValue
  }}</span>
  <span v-else-if="isBool" class="tableBoolCell">{{ boolValue }}</span>
  <span v-else class="tableTextCell" :title="textValue">{{ textValue }}</span>
</template>

<script>
import { mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import { getCoverSrc, getPlaceholderSrc } from "@/api/v3/browser";
import { DATE_FORMAT, getDateTime } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";

const M2M_COLUMNS = new Set([
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
]);
const BOOL_COLUMNS = new Set(["monochrome"]);
// Columns whose value is a byte count (rendered "1.2 MB"-style).
const SIZE_COLUMNS = new Set(["size"]);
// Columns whose value is a date-only ISO string (rendered locale-friendly).
const DATE_COLUMNS = new Set(["date"]);
// Columns whose value is a full ISO timestamp.
const DATETIME_COLUMNS = new Set([
  "created_at",
  "updated_at",
  "metadata_mtime",
  "bookmark_updated_at",
]);

function snakeToCamel(s) {
  return s.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

function formatSize(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "";
  return prettyBytes(value);
}

function formatDate(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return DATE_FORMAT.format(d);
}

function formatDateTime(value, twentyFourHour) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return getDateTime(d, twentyFourHour);
}

export default {
  name: "BrowserTableCell",
  props: {
    column: {
      type: String,
      required: true,
    },
    row: {
      type: Object,
      required: true,
    },
    coverSize: {
      type: String,
      default: "sm",
    },
    coverGroup: {
      type: String,
      default: "c",
    },
  },
  data() {
    return {
      /*
       * Once a cover URL fails (404 / network error) we swap to the
       * group's placeholder svg so the browser never renders the
       * broken-image icon. Reset when the row identity changes.
       */
      imgErrored: false,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
    }),
    placeholderSrc() {
      return getPlaceholderSrc(this.coverGroup);
    },
    coverSrc() {
      const { coverPk, coverCustomPk } = this.row;
      if (!coverPk && !coverCustomPk) {
        return this.placeholderSrc;
      }
      return getCoverSrc({ coverPk, coverCustomPk });
    },
    imgSrc() {
      return this.imgErrored ? this.placeholderSrc : this.coverSrc;
    },
    coverSizeClass() {
      return `tableCoverSize-${this.coverSize}`;
    },
    rowAttrName() {
      /*
       * Backend field names are snake_case (matches the column-registry
       * keys and the columns= query-param contract). DRF's camelcase
       * middleware converts them on the wire, so the row dict in the
       * browser uses camelCase. Translate here so callers don't have
       * to know about the encoding boundary.
       */
      return snakeToCamel(this.column);
    },
    rawValue() {
      const name = this.rowAttrName;
      if (!Object.hasOwn(this.row, name)) return undefined;
      // eslint-disable-next-line security/detect-object-injection
      return this.row[name];
    },
    isList() {
      return M2M_COLUMNS.has(this.column);
    },
    isBool() {
      return BOOL_COLUMNS.has(this.column);
    },
    listValue() {
      const value = this.rawValue;
      if (!Array.isArray(value) || value.length === 0) return "";
      return value.join(", ");
    },
    boolValue() {
      if (this.rawValue === true) return "Yes";
      if (this.rawValue === false) return "No";
      return "";
    },
    textValue() {
      const value = this.rawValue;
      if (value === null || value === undefined) return "";
      /*
       * Type-aware formatting for known columns. Everything else
       * stringifies straight through.
       */
      if (SIZE_COLUMNS.has(this.column)) return formatSize(value);
      if (DATE_COLUMNS.has(this.column)) return formatDate(value);
      if (DATETIME_COLUMNS.has(this.column)) {
        return formatDateTime(value, this.twentyFourHourTime);
      }
      return String(value);
    },
  },
  watch: {
    /*
     * Reset the error flag when the row changes (Vue reuses cell
     * instances across re-renders, so a fresh row gets a fresh chance).
     */
    "row.pk"() {
      this.imgErrored = false;
    },
  },
  methods: {
    onImgError() {
      this.imgErrored = true;
    },
  },
};
</script>

<style scoped lang="scss">
.tableCoverCell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tableCoverCell img {
  display: block;
  height: 100%;
  width: auto;
  border-radius: 2px;
  object-fit: cover;
}

.tableCoverSize-sm {
  height: 32px;
}

.tableListCell,
.tableTextCell {
  display: inline-block;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
</style>
