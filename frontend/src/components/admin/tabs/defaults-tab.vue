<!--
  Site-wide defaults for new sessions. Two sections, Browser and Reader,
  each with its own form and explicit Save / Revert: a default lands on
  every new visitor, so nothing saves on change. See DESIGN.md §6.
-->
<template>
  <div id="defaults" class="adminReadingColumn">
    <div v-if="!server">
      <v-progress-circular indeterminate />
    </div>
    <template v-else>
      <div class="adminProse">
        <p>
          New sessions start with these settings, and browser and reader resets
          restore them. A new user keeps the settings their session started
          with. Existing sessions keep theirs unless you also apply a change to
          existing anonymous sessions when you save.
        </p>
        <p>
          OPDS keeps the factory defaults, except its top collection. Folders
          can only be the top collection while Folder View is on.
        </p>
      </div>

      <v-form ref="browserForm" @submit.prevent="save('browser')">
        <AdminSection title="Browser">
          <template #actions>
            <v-btn variant="text" size="small" @click="fillFactory('browser')">
              Factory defaults
            </v-btn>
          </template>
          <div class="adminCard">
            <v-select
              v-model="draft.browser.topCollection"
              :items="topCollectionChoices"
              :item-props="topCollectionItemProps"
              label="Top Collection"
              density="compact"
              hide-details="auto"
              :error-messages="topCollectionErrors"
            />
          </div>
          <div class="adminCard">
            <div class="adminCardTitle">Show Collections</div>
            <div class="defaultsCheckRow">
              <v-checkbox
                v-for="item in showChoices"
                :key="item.key"
                v-model="draft.browser[item.key]"
                :label="item.title"
                :disabled="item.key === lockedShowKey"
                density="compact"
                hide-details
              />
            </div>
            <p v-if="lockedShowHint" class="adminHint">{{ lockedShowHint }}</p>
          </div>
          <div class="adminCard">
            <v-select
              v-model="draft.browser.orderBy"
              :items="orderByChoices"
              label="Order By"
              density="compact"
              hide-details="auto"
              :error-messages="fieldErrors.orderBy"
            />
            <v-checkbox
              v-model="draft.browser.orderReverse"
              label="Reverse Order"
              density="compact"
              hide-details
            />
          </div>
          <div class="adminCard">
            <v-select
              v-model="draft.browser.viewMode"
              :items="viewModeChoices"
              label="View Mode"
              density="compact"
              hide-details="auto"
            />
            <v-checkbox
              v-model="draft.browser.twentyFourHourTime"
              label="24 Hour Time"
              density="compact"
              hide-details
            />
            <v-checkbox
              v-model="draft.browser.alwaysShowFilename"
              label="Always Show Filename"
              density="compact"
              hide-details
            />
          </div>
          <div class="adminCard">
            <v-select
              v-model="draft.browser.bookmark"
              :items="bookmarkChoices"
              label="Bookmark Filter"
              density="compact"
              hide-details="auto"
              :error-messages="fieldErrors.bookmark"
            />
          </div>
          <div class="adminCard">
            <div class="adminCardTitle">Table Columns</div>
            <div class="adminCardDesc">
              A collection without its own columns shows the factory set.
              Visitors who pick their own columns for a collection keep them.
            </div>
            <div
              v-for="row in tableColumnRows"
              :key="row.collection"
              class="tableColumnsRow"
            >
              <span class="tableColumnsName">{{ row.title }}</span>
              <span class="tableColumnsCount">{{ row.summary }}</span>
              <span class="adminInlineActions">
                <v-btn
                  variant="text"
                  size="small"
                  @click="openPicker(row.collection)"
                >
                  Edit
                </v-btn>
                <v-btn
                  variant="text"
                  size="small"
                  :disabled="row.factory"
                  @click="clearColumns(row.collection)"
                >
                  Clear
                </v-btn>
              </span>
            </div>
            <div v-if="fieldErrors.tableColumns" class="saveErrors">
              <div
                v-for="(error, index) in fieldErrors.tableColumns"
                :key="index"
              >
                {{ error }}
              </div>
            </div>
          </div>
          <v-checkbox
            v-model="applyToAnonymous.browser"
            :label="applyLabel"
            density="compact"
            hide-details
          />
          <AdminActionBar
            save-text="Save Browser Defaults"
            :saving="saving.browser"
            :save-disabled="!hasBrowserChanges"
            :revert-disabled="!hasBrowserChanges || saving.browser"
            @revert="revert('browser')"
          />
        </AdminSection>
      </v-form>

      <v-form ref="readerForm" @submit.prevent="save('reader')">
        <AdminSection title="Reader">
          <template #actions>
            <v-btn variant="text" size="small" @click="fillFactory('reader')">
              Factory defaults
            </v-btn>
          </template>
          <div class="adminCard">
            <ReaderSettingsControls
              :settings="draft.reader"
              standalone
              @update="updateReader"
            />
          </div>
          <v-checkbox
            v-model="applyToAnonymous.reader"
            :label="applyLabel"
            density="compact"
            hide-details
          />
          <AdminActionBar
            save-text="Save Reader Defaults"
            :saving="saving.reader"
            :save-disabled="!hasReaderChanges"
            :revert-disabled="!hasReaderChanges || saving.reader"
            @revert="revert('reader')"
          />
        </AdminSection>
      </v-form>

      <div v-if="unboundErrors.length > 0" class="saveErrors">
        <div v-for="(error, index) in unboundErrors" :key="index">
          {{ error }}
        </div>
      </div>
      <div v-if="appliedMessage" class="appliedMessage">
        {{ appliedMessage }}
      </div>

      <BrowserTableColumnPicker
        v-model="picker.open"
        standalone
        :standalone-top-collection="picker.collection"
        :standalone-columns="picker.columns"
        :standalone-show="draftShow"
        @save="onColumnsSaved"
      />

      <v-dialog v-model="confirm.open" max-width="480">
        <div class="confirmApply">
          <div class="confirmApplyTitle">Apply to existing sessions</div>
          <p>
            Anonymous sessions still at the old default move to the new one.
            Sessions whose visitor changed a setting keep their own choice.
          </p>
          <ul>
            <li v-for="line in confirm.lines" :key="line.key">
              {{ line.label }}: {{ line.count }}
            </li>
          </ul>
          <p class="confirmApplyTotal">Up to {{ confirm.total }} updates.</p>
          <ConfirmFooter
            confirm-text="Save and Apply"
            @confirm="confirmApply"
            @cancel="confirm.open = false"
          />
        </div>
      </v-dialog>
    </template>
  </div>
</template>

<script>
import { dequal } from "dequal";
import { mapActions, mapState } from "pinia";

import BROWSER_CHOICES from "@/choices/browser-choices.json";
import AdminActionBar from "@/components/admin/tabs/action-bar.vue";
import AdminSection from "@/components/admin/tabs/admin-section.vue";
import BrowserTableColumnPicker from "@/components/browser/table/browser-table-column-picker.vue";
import ConfirmFooter from "@/components/confirm-footer.vue";
import ReaderSettingsControls from "@/components/reader/drawer/reader-settings-controls.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";
import { VERTICAL_READING_DIRECTIONS } from "@/stores/reader";

const SHOW_KEYS = Object.freeze({
  publishers: "showPublishers",
  imprints: "showImprints",
  series: "showSeries",
  volumes: "showVolumes",
});
const BROWSER_KEYS = Object.freeze([
  "topCollection",
  ...Object.values(SHOW_KEYS),
  "orderBy",
  "orderReverse",
  "viewMode",
  "twentyFourHourTime",
  "alwaysShowFilename",
  "bookmark",
  "tableColumns",
]);
const READER_KEYS = Object.freeze([
  "fitTo",
  "readingDirection",
  "twoPages",
  "pageTransition",
  "cacheBook",
]);
// The fields a catch-up moves, keyed as the reach counts are.
const REACH_LABELS = Object.freeze({
  topCollection: "Top Collection",
  show: "Show Collections",
  orderBy: "Order By",
  orderReverse: "Reverse Order",
  viewMode: "View Mode",
  twentyFourHourTime: "24 Hour Time",
  alwaysShowFilename: "Always Show Filename",
  bookmark: "Bookmark Filter",
  fitTo: "Display",
  readingDirection: "Reading Direction",
  twoPages: "Two Pages",
  pageTransition: "Animate Page Turns",
  cacheBook: "Cache Entire Book",
});
const SHOW_FIELDS = new Set(Object.values(SHOW_KEYS));
const EXCLUDED_ORDER_BY = new Set(BROWSER_CHOICES.EXTRA_SORT_UNSUPPORTED_KEYS);
const AUTOMATIC_ORDER_BY = Object.freeze({
  value: "",
  title: "Automatic (Name; Filename in Folders; Arc Number in Story Arcs)",
});
// The server errors a field of this tab shows next to its input.
const BOUND_ERROR_FIELDS = Object.freeze([
  "topCollection",
  "orderBy",
  "bookmark",
  "tableColumns",
]);

// JSON-safe values; structuredClone can't copy the reactive proxies.
const clone = (value) =>
  value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const pick = (source, keys) =>
  Object.fromEntries(keys.map((key) => [key, clone(source?.[key])]));
export const pickBrowser = (source) => pick(source, BROWSER_KEYS);
export const pickReader = (source) => pick(source, READER_KEYS);

/*
 * The reach keys of the fields a draft changes. The four show boxes move
 * as one ``show``; table columns have no catch-up, every session already
 * follows the site default for the collections it didn't customize.
 */
export function changedReachKeys(draft, server) {
  const keys = new Set();
  for (const [field, value] of Object.entries(draft)) {
    if (dequal(value, server?.[field])) continue;
    const key = SHOW_FIELDS.has(field) ? "show" : field;
    if (Object.hasOwn(REACH_LABELS, key)) keys.add(key);
  }
  return [...keys];
}

export default {
  name: "AdminDefaultsTab",
  components: {
    AdminActionBar,
    AdminSection,
    BrowserTableColumnPicker,
    ConfirmFooter,
    ReaderSettingsControls,
  },
  data() {
    return {
      draft: { browser: pickBrowser(undefined), reader: pickReader(undefined) },
      saving: { browser: false, reader: false },
      applyToAnonymous: { browser: false, reader: false },
      applyLabel: "Also apply to existing anonymous sessions",
      appliedMessage: "",
      picker: { open: false, collection: "", columns: [] },
      confirm: { open: false, section: "", data: {}, lines: [], total: 0 },
      topCollectionChoices: BROWSER_CHOICES.TOP_COLLECTION,
      showChoices: BROWSER_CHOICES.TOP_COLLECTION.filter(({ value }) =>
        Object.hasOwn(SHOW_KEYS, value),
      ).map(({ value, title }) => ({ key: SHOW_KEYS[value], title })),
      orderByChoices: Object.freeze([
        AUTOMATIC_ORDER_BY,
        ...BROWSER_CHOICES.ORDER_BY.filter(
          ({ value }) => !EXCLUDED_ORDER_BY.has(value),
        ),
      ]),
      viewModeChoices: BROWSER_CHOICES.VIEW_MODE,
      bookmarkChoices: BROWSER_CHOICES.BOOKMARK_FILTER,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      server: (state) => state.settingsDefaults,
      flags: (state) => state.flags,
    }),
    ...mapState(useCommonStore, {
      fieldErrors: (state) => state.form.fieldErrors ?? {},
    }),
    serverBrowser() {
      return this.server?.browser;
    },
    serverReader() {
      return this.server?.reader;
    },
    hasBrowserChanges() {
      return !dequal(this.draft.browser, pickBrowser(this.serverBrowser));
    },
    hasReaderChanges() {
      return !dequal(this.draft.reader, pickReader(this.serverReader));
    },
    folderViewOn() {
      const flag = (this.flags || []).find(({ key }) => key === "FV");
      // Startup seeds Folder View on; a missing row counts as on.
      return flag ? Boolean(flag.on) : true;
    },
    draftShow() {
      return Object.fromEntries(
        Object.entries(SHOW_KEYS).map(([collection, key]) => [
          collection,
          Boolean(this.draft.browser[key]),
        ]),
      );
    },
    // The current top collection's box: unchecking it would hide it.
    lockedShowKey() {
      return SHOW_KEYS[this.draft.browser.topCollection];
    },
    // Why the locked box is disabled, and how to free it.
    lockedShowHint() {
      const title = this.showChoices.find(
        ({ key }) => key === this.lockedShowKey,
      )?.title;
      if (!title) return "";
      return `${title} is the Top Collection, so it must stay shown. Choose another Top Collection to hide ${title}.`;
    },
    topCollectionErrors() {
      const reason = this.unavailableReason(this.draft.browser.topCollection);
      return reason ? [reason] : (this.fieldErrors.topCollection ?? []);
    },
    tableColumnRows() {
      const tableColumns = this.draft.browser.tableColumns || {};
      return this.topCollectionChoices.map(({ value, title }) => {
        const count = tableColumns[value]?.length ?? 0;
        return {
          collection: value,
          title,
          factory: count === 0,
          summary: count ? `${count} columns` : "Factory",
        };
      });
    },
    unboundErrors() {
      const bound = new Set(BOUND_ERROR_FIELDS);
      return Object.entries(this.fieldErrors)
        .filter(([field]) => !bound.has(field))
        .flatMap(([, messages]) => messages);
    },
  },
  watch: {
    /*
     * Per section, and only on a real change, so saving one section
     * doesn't throw away the other section's unsaved edits.
     */
    serverBrowser: {
      immediate: true,
      handler(to, from) {
        if (!dequal(to, from)) this.draft.browser = pickBrowser(to);
      },
    },
    serverReader: {
      immediate: true,
      handler(to, from) {
        if (!dequal(to, from)) this.draft.reader = pickReader(to);
      },
    },
  },
  mounted() {
    this.clearErrors();
    this.loadSettingsDefaults();
    // Folder View gates the folders top collection.
    this.loadTables(["Flag"]);
  },
  methods: {
    ...mapActions(useAdminStore, [
      "loadSettingsDefaults",
      "loadSettingsDefaultsReach",
      "loadTables",
      "updateSettingsDefaults",
    ]),
    ...mapActions(useCommonStore, ["clearErrors"]),
    unavailableReason(collection) {
      if (collection === "folders" && !this.folderViewOn) {
        return "Folder View is off on the Settings tab";
      }
      const showKey = SHOW_KEYS[collection];
      if (showKey && !this.draft.browser[showKey]) {
        return "Its Show Collections box is off";
      }
      return "";
    },
    topCollectionItemProps(item) {
      const subtitle = this.unavailableReason(item.value);
      return { disabled: Boolean(subtitle), subtitle };
    },
    fillFactory(section) {
      const factory = this.server?.factory?.[section];
      this.draft[section] =
        section === "browser" ? pickBrowser(factory) : pickReader(factory);
    },
    revert(section) {
      this.draft[section] =
        section === "browser"
          ? pickBrowser(this.serverBrowser)
          : pickReader(this.serverReader);
    },
    updateReader(updates) {
      const reader = { ...this.draft.reader, ...updates };
      // Two pages is a horizontal mode, as the reader enforces too.
      if (VERTICAL_READING_DIRECTIONS.has(reader.readingDirection)) {
        reader.twoPages = false;
      }
      this.draft.reader = reader;
    },
    openPicker(collection) {
      this.picker = {
        open: true,
        collection,
        columns: [...(this.draft.browser.tableColumns?.[collection] ?? [])],
      };
    },
    // An empty list means "factory", so it removes the key.
    onColumnsSaved(columns) {
      this.setColumns(this.picker.collection, columns);
    },
    clearColumns(collection) {
      this.setColumns(collection, []);
    },
    setColumns(collection, columns) {
      const { [collection]: _removed, ...rest } =
        this.draft.browser.tableColumns || {};
      this.draft.browser.tableColumns = columns.length
        ? { ...rest, [collection]: columns }
        : rest;
    },
    async save(section) {
      const form = this.$refs[`${section}Form`];
      if (form) {
        const { valid } = await form.validate();
        if (!valid) return;
      }
      const server =
        section === "browser" ? this.serverBrowser : this.serverReader;
      const data = { [section]: clone(this.draft[section]) };
      const reachKeys = this.applyToAnonymous[section]
        ? changedReachKeys(this.draft[section], server)
        : [];
      if (reachKeys.length === 0) {
        return this.put(section, data, false);
      }
      const reach = (await this.loadSettingsDefaultsReach()) ?? {};
      const lines = reachKeys.map((key) => ({
        key,
        label: REACH_LABELS[key],
        count: reach[key] ?? 0,
      }));
      const total = lines.reduce((sum, { count }) => sum + count, 0);
      this.confirm = { open: true, section, data, lines, total };
    },
    confirmApply() {
      const { section, data } = this.confirm;
      this.confirm.open = false;
      return this.put(section, data, true);
    },
    async put(section, data, applyToAnonymous) {
      this.saving[section] = true;
      this.appliedMessage = "";
      try {
        const applied = await this.updateSettingsDefaults(data, {
          applyToAnonymous,
        });
        if (applied === undefined) return;
        // Per Save: the next Save leaves existing sessions alone again.
        this.applyToAnonymous[section] = false;
        if (applyToAnonymous) {
          const moved = Object.values(applied).reduce((a, b) => a + b, 0);
          this.appliedMessage = `Applied ${moved} updates to existing anonymous sessions.`;
        }
      } finally {
        this.saving[section] = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as d;

.defaultsCheckRow {
  display: flex;
  flex-wrap: wrap;
  column-gap: d.$space-4;
}

.tableColumnsRow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  column-gap: d.$space-2;
  padding-top: d.$space-1;
}

.tableColumnsName {
  flex: 1 1 8em;
  min-width: 0;
}

.tableColumnsCount {
  color: rgb(var(--v-theme-text-secondary));
  font-size: d.$text-small;
}

.saveErrors {
  color: rgb(var(--v-theme-error));
  font-size: d.$text-small;
  padding-top: d.$space-1;
}

.appliedMessage {
  color: rgb(var(--v-theme-success));
  font-size: d.$text-small;
}

.confirmApply {
  padding: 20px;
  background-color: rgb(var(--v-theme-surface));
}

.confirmApplyTitle {
  padding-bottom: 10px;
  font-weight: bolder;
  font-size: larger;
  text-align: center;
}

.confirmApplyTotal {
  font-weight: 500;
}
</style>
