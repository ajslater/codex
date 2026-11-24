<template>
  <v-dialog v-model="show" max-width="960px" scrollable>
    <v-card>
      <v-card-title class="dialogTitle">
        {{ into ? `Add a source to ${into.name}` : "Add Reading Lists" }}
      </v-card-title>
      <v-card-text>
        <template v-if="!cards.length">
          <v-tabs v-model="tab" density="compact">
            <v-tab value="catalog">DieselTech Catalog</v-tab>
            <v-tab value="files">Files</v-tab>
            <v-tab value="url">URL</v-tab>
            <v-tab value="metron">Metron</v-tab>
            <v-tab value="arcs">Story Arcs</v-tab>
          </v-tabs>
          <v-window v-model="tab" class="tabWindow">
            <v-window-item value="metron">
              <p class="adminProse">
                Search Metron's reading lists by name. A list's issues arrive 50
                a page at Metron's rate limit, so they are fetched after Import,
                in the background.
              </p>
              <p v-if="!hasMetron" class="adminProse keyNeeded">
                {{ KEY_NEEDED.metron }}
              </p>
              <div class="searchRow">
                <v-text-field
                  v-model="metronQuery"
                  label="Name"
                  density="compact"
                  hide-details
                  :disabled="!hasMetron"
                  @keyup.enter="search('metron')"
                />
                <v-text-field
                  v-model="metronCurator"
                  label="Curator (cbro, cmro…)"
                  density="compact"
                  hide-details
                  class="curatorField"
                  :disabled="!hasMetron"
                  @keyup.enter="search('metron')"
                />
                <v-btn
                  variant="tonal"
                  size="small"
                  :loading="searching"
                  :disabled="!hasMetron"
                  :title="hasMetron ? '' : KEY_NEEDED.metron"
                  @click="search('metron')"
                >
                  Search
                </v-btn>
              </div>
              <v-data-table-virtual
                v-model="pickedMetron"
                :headers="metronHeaders"
                :items="metronResults"
                item-value="ref"
                show-select
                density="compact"
                height="320"
              >
                <template #[`item.name`]="{ item }">
                  {{ item.name }}
                  <v-chip v-if="item.imported" size="x-small">Imported</v-chip>
                </template>
              </v-data-table-virtual>
            </v-window-item>
            <v-window-item value="catalog">
              <p class="adminProse">
                The DieselTech catalog of ComicRack lists, read from GitHub.
                Leave the search empty to browse every list, then narrow by
                publisher.
              </p>
              <div class="searchRow">
                <v-text-field
                  v-model="catalogQuery"
                  label="Search"
                  density="compact"
                  hide-details
                  @keyup.enter="search('catalog')"
                />
                <v-select
                  v-model="catalogPublisher"
                  :items="catalogPublishers"
                  label="Publisher"
                  density="compact"
                  hide-details
                  clearable
                  class="curatorField"
                />
                <v-btn
                  variant="tonal"
                  size="small"
                  :loading="searching"
                  @click="search('catalog')"
                >
                  Search
                </v-btn>
              </div>
              <v-data-table-virtual
                v-model="pickedCatalog"
                :headers="catalogHeaders"
                :items="catalogShown"
                item-value="ref"
                show-select
                density="compact"
                height="320"
              >
                <template #[`item.name`]="{ item }">
                  {{ item.name }}
                  <v-chip v-if="item.updated" size="x-small" color="primary">
                    Newer revision
                  </v-chip>
                  <v-chip v-else-if="item.imported" size="x-small">
                    Imported
                  </v-chip>
                </template>
              </v-data-table-virtual>
            </v-window-item>
            <v-window-item value="files">
              <p class="adminProse">
                ComicRack <code class="adminCode">.cbl</code> or json-cbl
                reading lists. Several at once.
              </p>
              <v-file-input
                v-model="files"
                label="Reading list files"
                accept=".cbl,.json,.xml"
                multiple
                chips
                density="compact"
              />
            </v-window-item>
            <v-window-item value="url">
              <p class="adminProse">
                One address per line. Each is fetched now, by the server.
              </p>
              <v-textarea
                v-model="urls"
                label="URLs"
                rows="4"
                density="compact"
              />
            </v-window-item>
            <v-window-item value="arcs">
              <p class="adminProse">
                A database's own story arc, one per line. Its issues are fetched
                after Import. Comic Vine names an arc's issues by id alone, so
                its missing issues read poorly; a curated list of the same arc,
                combined with it, fills in their names.
              </p>
              <v-textarea
                v-model="metronArcs"
                label="Metron arc ids"
                rows="2"
                density="compact"
                :disabled="!hasMetron"
                :hint="hasMetron ? '' : KEY_NEEDED.metron"
                persistent-hint
              />
              <v-textarea
                v-model="comicvineArcs"
                label="Comic Vine arc ids or addresses"
                :disabled="!hasComicvine"
                :hint="
                  hasComicvine
                    ? 'An address like comicvine.gamespot.com/civil-war/4045-55766/'
                    : KEY_NEEDED.comicvine
                "
                persistent-hint
                rows="2"
                density="compact"
              />
            </v-window-item>
          </v-window>
        </template>
        <template v-else>
          <p class="adminProse">
            Nothing is saved yet. Choose for each list where it goes, then
            Import.
          </p>
          <PreviewCard
            v-for="card in cards"
            :key="card.token || `${card.kind}:${card.ref}`"
            v-model="choices[cardKey(card)]"
            :card="card"
            :into="into"
          />
        </template>
      </v-card-text>
      <v-card-actions>
        <v-btn v-if="cards.length" variant="text" @click="cards = []">
          Back
        </v-btn>
        <span v-if="!cards.length && pickedCount" class="pickSummary">
          {{ pickSummary }}
        </span>
        <!-- Why Preview or Import is off, in words: a title never shows. -->
        <span v-else-if="!cards.length" class="pickSummary">
          {{ pickNoneHint }}
        </span>
        <span v-else-if="!importable" class="pickSummary">
          {{ importNoneHint }}
        </span>
        <v-spacer />
        <v-btn variant="text" @click="show = false">Cancel</v-btn>
        <v-btn
          v-if="!cards.length"
          variant="tonal"
          :loading="previewing"
          :disabled="!pickedCount"
          @click="preview"
        >
          Preview {{ pickedCount || "" }}
        </v-btn>
        <v-btn
          v-else
          variant="tonal"
          :loading="importing"
          :disabled="!importable"
          @click="doImport"
        >
          Import
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapState } from "pinia";

import * as API from "@/api/v4/reading-lists";
import PreviewCard from "@/components/admin/tabs/reading-lists/preview-card.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const METRON_HEADERS = Object.freeze([
  { title: "Name", key: "name" },
  { title: "Type", key: "listType" },
  { title: "Curator", key: "curator" },
  { title: "By", key: "username" },
  { title: "Rating", key: "rating" },
]);
// A Comic Vine arc's id, alone or in its address (…/4045-55766/).
const COMICVINE_ARC_RE = /(?:^|4045-)(\d+)\/?$/;
const METRON_ARC_RE = /^(\d+)$/;

/*
 * The ids a textarea holds, one per line, by ``pattern``'s first group.
 * Lines that are not an id are skipped.
 */
const arcIds = (text, pattern) =>
  text
    .split("\n")
    .map((line) => pattern.exec(line.trim())?.[1])
    .filter(Boolean);

// Why a database's inputs are off, and where to turn them on.
const KEY_NEEDED = Object.freeze({
  metron:
    "Needs a Metron API key: add one in Admin › Tagging, under Online Sources.",
  comicvine:
    "Needs a Comic Vine API key: add one in Admin › Tagging, under Online Sources.",
});

const plural = (count, one, many) => `${count} ${count === 1 ? one : many}`;

const CATALOG_HEADERS = Object.freeze([
  { title: "Name", key: "name" },
  { title: "Publisher", key: "publisher" },
  { title: "Category", key: "category" },
  { title: "Curator", key: "curator" },
]);

export default {
  name: "AddListsDialog",
  components: { PreviewCard },
  props: {
    modelValue: { type: Boolean, default: false },
    // A list to add the picked lists to as sources, or null for new lists.
    into: { type: Object, default: null },
  },
  emits: ["update:modelValue", "imported"],
  data() {
    return {
      KEY_NEEDED,
      tab: "catalog",
      metronHeaders: METRON_HEADERS,
      catalogHeaders: CATALOG_HEADERS,
      metronQuery: "",
      metronCurator: "",
      metronResults: [],
      pickedMetron: [],
      catalogQuery: "",
      catalogPublisher: null,
      catalogResults: [],
      pickedCatalog: [],
      files: [],
      urls: "",
      metronArcs: "",
      comicvineArcs: "",
      searching: false,
      previewing: false,
      importing: false,
      cards: [],
      pickNoneHint: "Pick at least one list on any tab.",
      importNoneHint: "Every list here failed to load.",
      choices: {},
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      hasMetron: (state) =>
        Boolean(state.taggingDefaults?.hasMetronCredentials),
      hasComicvine: (state) =>
        Boolean(state.taggingDefaults?.hasComicvineCredentials),
    }),
    pickSummary() {
      // What is picked on every tab, not only the one showing.
      const parts = [
        [this.pickedCatalog.length, "catalog list", "catalog lists"],
        [this.files?.length || 0, "file", "files"],
        [this.urlList.length, "URL", "URLs"],
        [this.pickedMetron.length, "Metron list", "Metron lists"],
        [
          this.metronArcIds.length + this.comicvineArcIds.length,
          "story arc",
          "story arcs",
        ],
      ]
        .filter(([count]) => count)
        .map(([count, one, many]) => plural(count, one, many));
      return `Picked: ${parts.join(", ")}`;
    },
    show: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit("update:modelValue", value);
      },
    },
    urlList() {
      return this.urls
        .split("\n")
        .map((url) => url.trim())
        .filter(Boolean);
    },
    metronArcIds() {
      return arcIds(this.metronArcs, METRON_ARC_RE);
    },
    comicvineArcIds() {
      return arcIds(this.comicvineArcs, COMICVINE_ARC_RE);
    },
    pickedCount() {
      return (
        this.pickedMetron.length +
        this.pickedCatalog.length +
        (this.files?.length || 0) +
        this.urlList.length +
        this.metronArcIds.length +
        this.comicvineArcIds.length
      );
    },
    catalogPublishers() {
      return [
        ...new Set(this.catalogResults.map((row) => row.publisher)),
      ].filter(Boolean);
    },
    catalogShown() {
      if (!this.catalogPublisher) return this.catalogResults;
      return this.catalogResults.filter(
        (row) => row.publisher === this.catalogPublisher,
      );
    },
    importable() {
      return this.cards.some((card) => !card.error);
    },
  },
  watch: {
    modelValue: {
      immediate: true,
      handler(value) {
        if (value) this.open();
      },
    },
  },
  methods: {
    open() {
      this.reset();
      this.tab = "catalog";
      useAdminStore().loadTaggingDefaults();
      // The catalog lists itself: browse first, search to narrow.
      if (!this.catalogResults.length) this.search("catalog");
    },
    reset() {
      this.cards = [];
      this.choices = {};
      this.pickedMetron = [];
      this.pickedCatalog = [];
      this.files = [];
      this.urls = "";
      this.metronArcs = "";
      this.comicvineArcs = "";
    },
    cardKey(card) {
      return card.token || `${card.kind}:${card.ref}`;
    },
    async search(source) {
      this.searching = true;
      try {
        const query =
          source === "metron" ? this.metronQuery : this.catalogQuery;
        const response = await API.searchLists(
          source,
          query,
          source === "metron" ? this.metronCurator : "",
        );
        const results = response.data.results || [];
        if (source === "metron") this.metronResults = results;
        else this.catalogResults = results;
      } catch (error) {
        useCommonStore().setErrorNotice(error);
      } finally {
        this.searching = false;
      }
    },
    sources() {
      const metron = this.metronResults
        .filter((row) => this.pickedMetron.includes(row.ref))
        .map((row) => ({
          kind: "metron_list",
          ref: row.ref,
          name: row.name,
          curator: row.curator,
          listType: row.listType,
          private: Boolean(row.private),
        }));
      const catalog = this.catalogResults
        .filter((row) => this.pickedCatalog.includes(row.ref))
        .map((row) => ({ kind: "catalog", ref: row.ref, sha: row.sha }));
      const urls = this.urlList.map((ref) => ({ kind: "url", ref }));
      const arcs = [
        ...this.metronArcIds.map((ref) => ({
          kind: "metron_arc",
          ref,
          name: `Metron arc ${ref}`,
        })),
        ...this.comicvineArcIds.map((ref) => ({
          kind: "comicvine_arc",
          ref,
          name: `Comic Vine arc ${ref}`,
        })),
      ];
      return [...metron, ...catalog, ...urls, ...arcs];
    },
    async preview() {
      this.previewing = true;
      try {
        const response = await API.previewLists(
          this.files || [],
          this.sources(),
        );
        this.cards = response.data.cards || [];
        const choices = {};
        for (const card of this.cards) {
          const suggestion = (card.suggestions || []).find((s) => s.combine);
          choices[this.cardKey(card)] = {
            into: this.into?.pk || suggestion?.pk || null,
            // A list its Metron curator keeps private stays private.
            private: Boolean(card.private),
            name: "",
          };
        }
        this.choices = choices;
      } catch (error) {
        useCommonStore().setErrorNotice(error);
      } finally {
        this.previewing = false;
      }
    },
    async doImport() {
      this.importing = true;
      const items = this.cards
        .filter((card) => !card.error)
        .map((card) => {
          const choice = this.choices[this.cardKey(card)] || {};
          const base = card.token
            ? { token: card.token }
            : { kind: card.kind, ref: card.ref };
          return { ...base, ...choice };
        });
      try {
        const response = await API.importLists(items);
        const { queued = 0, fetching = 0 } = response.data || {};
        let message = `Importing ${queued + fetching} reading lists.`;
        if (fetching) message += " Metron and Comic Vine lists fetch first.";
        useCommonStore().setNotice(message);
        this.$emit("imported");
        this.show = false;
      } catch (error) {
        useCommonStore().setErrorNotice(error);
      } finally {
        this.importing = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as *;

@layer codex-components {
  .tabWindow {
    margin-top: $space-3;
  }

  .searchRow {
    display: flex;
    align-items: center;
    gap: $space-2;
    margin-bottom: $space-2;
  }

  .keyNeeded {
    color: rgb(var(--v-theme-warning));
  }

  .pickSummary {
    color: rgb(var(--v-theme-text-secondary));
    font-size: 0.85em;
    padding-left: 8px;
  }

  .curatorField {
    max-width: 220px;
  }

  .dialogTitle {
    font-weight: bold;
  }
}
</style>
