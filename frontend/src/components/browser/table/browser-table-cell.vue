<template>
  <span
    v-if="column === 'cover'"
    class="tableCoverCell"
    :class="coverSizeClass"
    @click.stop
  >
    <!-- The crop and radius go in as a style object, not a class:
         CoverPopup renders a VMenu fragment, which a scoped parent class
         cannot reach. The key resets the popup when Vue reuses this cell
         instance for a different row. -->
    <CoverPopup
      :key="row.pk"
      :thumb-src="imgSrc"
      :full-src="imgErrored ? '' : coverSrc"
      :alt="row.name || ''"
      :title="row.name || ''"
      thumb-height="100%"
      :style="THUMB_STYLE"
      loading="eager"
      @error="onImgError"
    />
  </span>
  <span v-else-if="column === 'favorite'" class="tableFavoriteCell" @click.stop>
    <FavoriteToggle
      v-if="favoritePk"
      :collection="favoriteCollection"
      :pk="favoritePk"
    />
  </span>
  <span v-else-if="isList" class="tableListCell" :title="listValue">{{
    listValue
  }}</span>
  <span v-else-if="isBool" class="tableBoolCell">{{ boolValue }}</span>
  <span
    v-else-if="column === 'issue'"
    class="tableIssueCell"
    :title="issueTitle"
  >
    <span class="tableIssueNumber">{{ issueValue.number }}</span
    ><span class="tableIssueSuffix">{{ issueValue.suffix }}</span>
  </span>
  <span v-else class="tableTextCell" :title="textValue">{{ textValue }}</span>
</template>

<script>
import { mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import { getCoverSrc, getPlaceholderSrc } from "@/api/v4/browser";
import { READING_DIRECTION } from "@/choices/reader-map.json";
import CoverPopup from "@/components/cover-popup.vue";
import FavoriteToggle from "@/components/favorite-toggle.vue";
import { DATE_FORMAT, getDateTime } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";

// What .tableCoverThumb used to say, minus the height the size class
// still owns. Inline because CoverPopup's menu branch is a fragment and
// a scoped class would never land on the image. The width stays auto so
// the cover keeps its own aspect ratio, which is also why the thumb
// loads eagerly — see CoverPopup's `loading` prop.
const THUMB_STYLE = Object.freeze({
  width: "auto",
  borderRadius: "2px",
  objectFit: "cover",
});

const M2M_COLUMNS = new Set([
  "characters",
  "credits",
  "genres",
  "identifiers",
  "locations",
  "reprints",
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
/*
 * Columns whose stored value is an enum code (ltr / rtl / …) and
 * should be expanded to its display label via a build-choices map.
 */
const ENUM_COLUMN_LABELS = Object.freeze({
  reading_direction: READING_DIRECTION,
});

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
  components: {
    CoverPopup,
    FavoriteToggle,
  },
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
    coverCollection: {
      type: String,
      default: "c",
    },
  },
  data() {
    return {
      /*
       * Once a cover URL fails (404 / network error) we swap to the
       * collection's placeholder svg so the browser never renders the
       * broken-image icon. Reset when the row identity changes.
       */
      imgErrored: false,
      THUMB_STYLE,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
    }),
    placeholderSrc() {
      return getPlaceholderSrc(this.coverCollection);
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
    favoriteCollection() {
      /*
       * Collection rows carry an explicit ``collection``; comic rows
       * omit it (the table view's lone comic-only top-collection) and
       * default to ``comics``.
       */
      return this.row?.collection ?? "comics";
    },
    favoritePk() {
      /*
       * Comic rows expose ``pk`` directly; collection rows use ``ids``
       * and only the single-id case can be favorited atomically.
       */
      const ids = this.row?.ids;
      if (Array.isArray(ids) && ids.length === 1) return ids[0];
      if (Array.isArray(ids)) return undefined;
      return this.row?.pk;
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
    issueValue() {
      /*
       * Backend emits the compound issue column as
       * ``{number, suffix}`` so the cell can split-justify the
       * halves. Defensive default keeps the template safe if a
       * stale/legacy payload arrives as a plain string.
       */
      const value = this.rawValue;
      if (value && typeof value === "object") {
        return {
          number: value.number || "",
          suffix: value.suffix || "",
        };
      }
      return { number: value ? String(value) : "", suffix: "" };
    },
    issueTitle() {
      const { number, suffix } = this.issueValue;
      return `${number}${suffix}`;
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
      /*
       * Enum columns store a code (ltr / rtl / ttb / btt for
       * ``reading_direction``); look up the display label, falling
       * back to the raw code if the map doesn't have an entry.
       */
      if (Object.hasOwn(ENUM_COLUMN_LABELS, this.column)) {
        const labels = ENUM_COLUMN_LABELS[this.column];
        if (Object.hasOwn(labels, value)) {
          return labels[value];
        }
        return String(value);
      }
      if (DATETIME_COLUMNS.has(this.column)) {
        return formatDateTime(value, this.twentyFourHourTime);
      }
      return String(value);
    },
  },
  watch: {
    /*
     * Reset the error flag when the row changes: Vue reuses cell
     * instances across re-renders, so a fresh row gets a fresh chance.
     * The popup dismisses itself — CoverPopup is keyed on the same pk.
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

.tableFavoriteCell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tableCoverSize-sm {
  height: 32px;
}

/*
 * Wrap-and-grow: long values fill the column up to a generous
 * max-width and wrap to as many as 3 lines, then clamp with an
 * ellipsis on the last line. The native ``:title`` tooltip still
 * carries the full value for cells that did get clipped.
 *
 * ``-webkit-line-clamp`` is the de-facto cross-browser way to do
 * multi-line ellipsis (Chrome, Safari, Firefox 68+, Edge); it
 * requires ``display: -webkit-box`` plus ``-webkit-box-orient``.
 * ``overflow-wrap: break-word`` lets unusually long unbreakable
 * tokens (long URLs in identifiers, no-space file names) wrap
 * rather than blow the column wide.
 */
.tableListCell,
.tableTextCell {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  max-width: 360px;
  overflow: hidden;
  overflow-wrap: break-word;
  vertical-align: middle;
}

/*
 * Compound issue cell: the number and suffix render as two halves
 * of the same cell. Number is right-justified in the left half so
 * digit columns line up at the boundary; suffix is left-justified
 * in the right half so it flows away from the number. With nothing
 * between them the two halves visually fuse into one value, but
 * stay aligned across rows even when only one half is present.
 */
.tableIssueCell {
  display: inline-flex;
  width: 100%;
  align-items: baseline;
  white-space: nowrap;
  vertical-align: middle;
}

.tableIssueNumber,
.tableIssueSuffix {
  flex: 1 1 50%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tableIssueNumber {
  text-align: right;
}

.tableIssueSuffix {
  text-align: left;
}
</style>
