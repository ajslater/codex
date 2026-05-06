<template>
  <div id="browserTable">
    <table class="browserTableTable">
      <thead>
        <tr>
          <th
            v-for="col in visibleColumns"
            :key="col"
            :class="{ sortable: isSortable(col), sorted: isSortedBy(col) }"
            @click="onHeaderClick(col)"
          >
            <span>{{ labelFor(col) }}</span>
            <v-icon v-if="isSortedBy(col)" size="14">
              {{ orderReverse ? mdiArrowDown : mdiArrowUp }}
            </v-icon>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="rowKey(row)"
          class="browserTableRow"
          @click="onRowClick(row)"
        >
          <td v-for="col in visibleColumns" :key="col">
            <BrowserTableCell
              :column="col"
              :row="row"
              :cover-size="coverSize"
              :cover-group="coverGroupFor(row)"
            />
          </td>
        </tr>
      </tbody>
    </table>
    <BrowserEmptyState v-if="rows.length === 0" />
  </div>
</template>

<script>
import { mdiArrowDown, mdiArrowUp } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import BrowserEmptyState from "@/components/browser/empty.vue";
import BrowserTableCell from "@/components/browser/table/browser-table-cell.vue";
import BROWSER_TABLE_COLUMNS from "@/choices/browser-table-columns.json";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserTable",
  components: {
    BrowserEmptyState,
    BrowserTableCell,
  },
  data() {
    return {
      mdiArrowDown,
      mdiArrowUp,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      orderBy: (state) => state.settings.orderBy,
      orderReverse: (state) => state.settings.orderReverse,
      coverSize: (state) => state.settings.tableCoverSize,
      pageData: (state) => state.page,
    }),
    rows() {
      /*
       * Backend emits ``rows`` for table mode, ``groups``/``books`` for
       * cover mode. Be tolerant: mid-toggle the store may briefly hold
       * a cover-shaped page, so fall back to the concatenated list.
       */
      const page = this.pageData;
      if (Array.isArray(page?.rows)) return page.rows;
      const groups = page?.groups ?? [];
      const books = page?.books ?? [];
      return [...groups, ...books];
    },
    visibleColumns() {
      return useBrowserStore()._resolveTableColumns();
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    columnEntry(column) {
      /*
       * The registry JSON is a frozen build artifact with a fixed key
       * set. The eslint rule can't see that, so the access is gated
       * behind ``Object.hasOwn`` and the bracket index is acknowledged
       * with the inline disable.
       */
      if (!Object.hasOwn(BROWSER_TABLE_COLUMNS, column)) return undefined;
      // eslint-disable-next-line security/detect-object-injection
      return BROWSER_TABLE_COLUMNS[column];
    },
    labelFor(column) {
      return this.columnEntry(column)?.label ?? column;
    },
    sortKeyFor(column) {
      return this.columnEntry(column)?.sort_key ?? null;
    },
    isSortable(column) {
      return Boolean(this.sortKeyFor(column));
    },
    isSortedBy(column) {
      const key = this.sortKeyFor(column);
      return key !== null && key === this.orderBy;
    },
    onHeaderClick(column) {
      const sortKey = this.sortKeyFor(column);
      if (!sortKey) return;
      if (this.orderBy === sortKey) {
        this.setSettings({ orderReverse: !this.orderReverse });
      } else {
        this.setSettings({ orderBy: sortKey, orderReverse: false });
      }
    },
    rowKey(row) {
      /*
       * ``rowKey`` matches the BrowserCard's ``${item.group}${item.ids}``
       * shape so vue's diff is stable across re-renders.
       */
      if (row.group !== undefined) return `${row.group}${row.ids ?? ""}`;
      return `c${row.pk}`;
    },
    coverGroupFor(row) {
      return row.group ?? "c";
    },
    onRowClick(row) {
      /*
       * Comic rows -> reader; group rows -> drill in. Mirrors the
       * navigation contract of <BrowserCard> so the table behaves as
       * an alternate presentation, not an alternate router.
       */
      const group = row.group ?? "c";
      const pks = row.ids ?? [row.pk];
      const path =
        group === "c" ? `/c/${pks[0]}/1` : `/${group}/${pks.join(",")}/1`;
      this.$router.push(path);
    },
  },
};
</script>

<style scoped lang="scss">
/*
 * #browserTable is the scroll container. It's a flex child of
 * #browsePane (flex-direction:column, padding-top reserves the
 * toolbar space). flex:1 + min-height:0 gives it a constrained
 * height inside the flex parent; overflow-y:auto makes it the
 * scroller. Sticky thead binds to this scroller, not to any
 * Vuetify-managed wrapper — that's the reason this is a plain
 * <table> instead of <v-table fixed-header>: v-table puts
 * overflow on its own internal wrapper which makes the sticky
 * behavior unreliable when the page already has its own scroll
 * pane.
 */
#browserTable {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.browserTableTable {
  width: 100%;
  border-collapse: collapse;
  background-color: rgb(var(--v-theme-surface));
}

.browserTableTable thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background-color: rgb(var(--v-theme-surface));
  padding: 6px 12px;
  text-align: left;
  font-weight: 600;
  font-size: 0.85em;
  color: rgb(var(--v-theme-textSecondary));
  white-space: nowrap;
  user-select: none;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.browserTableTable thead th.sortable {
  cursor: pointer;
}

.browserTableTable thead th.sortable:hover {
  color: rgb(var(--v-theme-primary));
}

.browserTableTable thead th.sorted {
  color: rgb(var(--v-theme-primary));
}

.browserTableTable td {
  padding: 6px 12px;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.12);
}

.browserTableRow {
  cursor: pointer;
}

.browserTableRow:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
