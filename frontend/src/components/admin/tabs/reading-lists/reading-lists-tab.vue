<template>
  <div>
    <AdminSection
      class="adminReadingColumn"
      title="Reading Lists"
      hint="Import reading lists from files, URLs, the DieselTech catalog, Metron and Comic Vine; combine lists of one event; and review how their issues match your comics. Lists from story arc tags appear here on their own. Everything is saved in Codex only, until you write a list into its comics' files."
    >
      <template #actions>
        <v-btn size="small" variant="tonal" @click="openAdd(null)">
          <v-icon start>{{ mdiPlaylistPlus }}</v-icon>
          Add Lists
        </v-btn>
      </template>
      <div v-if="suggestions.length" class="suggestionLine">
        <v-btn
          size="small"
          variant="text"
          @click="showSuggestions = !showSuggestions"
        >
          {{ suggestions.length }} suggested
          {{ suggestions.length === 1 ? "combination" : "combinations" }}
        </v-btn>
      </div>
      <div v-if="showSuggestions" class="adminCard suggestionCard">
        <div
          v-for="suggestion in suggestions"
          :key="`${suggestion.pk}-${suggestion.otherPk}`"
          class="suggestionRow"
        >
          <span>
            <strong>{{ suggestion.name }}</strong> and
            <strong>{{ suggestion.otherName }}</strong> read as one order ({{
              Math.round(suggestion.overlap * 100)
            }}% shared).
          </span>
          <v-btn
            size="small"
            variant="tonal"
            @click="openCombine([suggestion.pk, suggestion.otherPk])"
          >
            Combine
          </v-btn>
        </div>
      </div>
      <div v-if="errorCount" class="adminCard errorCard">
        <AdminExpandToggle
          v-model="showErrors"
          :label="`${errorCount} fetch or import ${errorCount === 1 ? 'error' : 'errors'}`"
        />
        <div v-if="showErrors">
          <div v-for="(error, index) in errors" :key="index" class="errorRow">
            <code class="adminCode">{{ error.kind }}:{{ error.ref }}</code>
            {{ error.error }}
          </div>
          <v-btn size="small" variant="text" @click="clearErrors">Clear</v-btn>
        </div>
      </div>
      <div v-if="listStatuses.length" class="adminCard progressCard">
        <StatusListItem
          v-for="status of listStatuses"
          :key="status.id"
          :status="status"
          :now="now"
        />
      </div>
      <div class="adminCard mappingsCard">
        <AdminExpandToggle v-model="showMappings" :label="mappingsLabel" />
        <div v-if="showMappings">
          <p class="adminProse">
            A mapping says a list's series is a library series. Review saves
            one; every list then matches that series' issues in it.
          </p>
          <div v-if="!mappings.length" class="adminNoData">
            No saved series mappings.
          </div>
          <div v-for="mapping in mappings" :key="mapping.pk" class="mappingRow">
            <span>
              <code class="adminCode">{{ mapping.seriesKey }}</code>
              <span v-if="mapping.year"> ({{ mapping.year }})</span>
              → {{ mapping.series.name }}
              <span v-if="mapping.series.startYear">
                ({{ mapping.series.startYear }})</span
              >
              <span v-if="mapping.series.publisher" class="mappingPublisher">
                {{ mapping.series.publisher }}
              </span>
            </span>
            <v-btn
              :icon="mdiTrashCanOutline"
              size="small"
              density="compact"
              variant="text"
              title="Forget this mapping. Issues it matched keep their comics."
              @click="deleteMapping(mapping.pk)"
            />
          </div>
        </div>
      </div>
    </AdminSection>

    <div class="filters">
      <v-text-field
        v-model="search"
        label="Name"
        density="compact"
        hide-details
        clearable
        class="nameFilter"
      />
      <!--
        Checklists, as the browser's filters: tick any number of rows, and
        a list shows if it matches any of them. Nothing ticked is every
        list.
      -->
      <v-select
        v-model="kindFilter"
        :items="kindItems"
        label="Source"
        density="compact"
        hide-details
        clearable
        multiple
        class="checklistFilter"
      >
        <template #selection="{ item, index }">
          <span v-if="index === 0" class="checklistSelection">{{
            item.name
          }}</span>
          <span v-else-if="index === 1" class="checklistMore">
            +{{ kindFilter.length - 1 }}
          </span>
        </template>
      </v-select>
      <v-select
        v-model="ownerFilter"
        :items="ownerItems"
        label="Visibility"
        density="compact"
        hide-details
        clearable
        multiple
        class="checklistFilter"
      >
        <template #selection="{ item, index }">
          <span v-if="index === 0" class="checklistSelection">{{
            item.name
          }}</span>
          <span v-else-if="index === 1" class="checklistMore">
            +{{ ownerFilter.length - 1 }}
          </span>
        </template>
      </v-select>
      <v-checkbox
        v-model="missingOnly"
        label="Has missing issues"
        density="compact"
        hide-details
      />
      <v-checkbox
        v-model="reviewOnly"
        label="Needs review"
        density="compact"
        hide-details
      />
    </div>

    <div v-if="selected.length" class="bulkBar">
      <span class="bulkCount">{{ selected.length }} selected</span>
      <v-btn
        size="small"
        variant="tonal"
        :disabled="selected.length < 2"
        @click="openCombine(selected)"
      >
        Combine
      </v-btn>
      <v-btn size="small" variant="text" @click="bulk('refresh')">
        Refresh
      </v-btn>
      <v-btn size="small" variant="text" @click="bulk('rematch')">
        Rematch
      </v-btn>
      <v-btn size="small" variant="text" @click="bulk('complete')">
        Complete from Metron or Comic Vine
      </v-btn>
      <v-btn
        size="small"
        variant="text"
        :disabled="!selectedWritable.length"
        @click="confirmWrite(selectedWritable)"
      >
        Write to Files
      </v-btn>
      <ConfirmDialog
        button-text="Delete"
        color="error"
        size="small"
        variant="text"
        confirm-text="Delete"
        title-text="Delete reading lists"
        :text="`Delete ${selected.length} reading lists? Lists from story arc tags come back on the next import. No comic file changes.`"
        @confirm="bulk('delete')"
      />
      <!-- Why a button here is off, in words: a title never shows. -->
      <p v-if="bulkHints.length" class="adminHint bulkHint">
        {{ bulkHints.join(" ") }}
      </p>
    </div>

    <AdminTable
      v-model="selected"
      :headers="headers"
      :items="filteredLists"
      :loading="!listsLoaded"
      show-select
    >
      <template #no-data>
        <td class="adminNoData" colspan="100%">{{ noDataText }}</td>
      </template>
      <template #[`item.name`]="{ item }">
        <div class="nameCell">
          <span>{{ item.name }}</span>
          <span v-if="item.listType" class="listType">{{
            listTypeLabel(item.listType)
          }}</span>
        </div>
      </template>
      <template #[`item.sources`]="{ item }">
        <v-chip
          v-for="source in item.sources"
          :key="source.pk"
          size="x-small"
          variant="tonal"
          class="sourceChip"
          :title="source.ref"
        >
          {{ sourceLabel(source) }}
        </v-chip>
      </template>
      <template #[`item.coverage`]="{ item }">
        <div
          class="coverage"
          :title="`${item.matched} of ${item.total} in your library`"
        >
          <v-progress-linear
            :model-value="item.total ? (100 * item.matched) / item.total : 0"
            height="6"
            rounded
          />
          <span class="coverageText"
            >{{ item.matched }} / {{ item.total }}</span
          >
        </div>
      </template>
      <template #[`item.needsReview`]="{ item }">
        <v-btn
          v-if="item.needsReview"
          size="small"
          variant="text"
          color="primary"
          @click="openReview(item, 'review')"
        >
          {{ item.needsReview }}
        </v-btn>
        <span v-else class="none">0</span>
      </template>
      <template #[`item.owner`]="{ item }">
        {{ item.owner ? item.owner : "Global" }}
      </template>
      <template #[`item.updatedAt`]="{ item }">
        <DateTimeColumn :dttm="item.updatedAt" />
      </template>
      <template #[`item.actions`]="{ item }">
        <span class="adminActionCell">
          <v-btn
            :icon="mdiFormatListChecks"
            size="small"
            density="compact"
            variant="text"
            title="Review"
            @click="openReview(item, 'all')"
          />
          <v-btn
            :icon="mdiSourceBranch"
            size="small"
            density="compact"
            variant="text"
            title="Sources"
            @click="openSources(item)"
          />
          <v-menu>
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                :icon="mdiDotsVertical"
                size="small"
                density="compact"
                variant="text"
                title="More"
              />
            </template>
            <v-list density="compact">
              <v-list-item title="Edit Details" @click="openDetails(item)" />
              <v-list-item title="Refresh" @click="act(item.pk, 'refresh')" />
              <v-list-item title="Rematch" @click="act(item.pk, 'rematch')" />
              <v-list-item
                :disabled="!item.completeFrom"
                :title="completeTitle(item)"
                :subtitle="
                  item.completeFrom
                    ? ''
                    : 'Needs a list from story arc tags with a Metron or Comic Vine arc id.'
                "
                @click="act(item.pk, 'complete')"
              />
              <v-list-item
                v-if="item.owner"
                title="Copy to Global"
                :subtitle="`Leaves ${item.owner}'s list as it is.`"
                @click="copyToGlobal(item.pk)"
              />
              <v-list-item
                :title="item.owner ? 'Make Global' : 'Make Private to Me'"
                :subtitle="
                  item.owner
                    ? `Moves it: ${item.owner} can no longer edit it.`
                    : ''
                "
                @click="setPrivate(item.pk, !item.owner)"
              />
              <v-list-item
                :disabled="!isWritable(item)"
                title="Write to Files"
                :subtitle="writeHint(item)"
                @click="confirmWrite([item])"
              />
              <ReadingListExportMenu :pk="item.pk" />
            </v-list>
          </v-menu>
          <ConfirmDialog
            :icon="mdiTrashCanOutline"
            size="small"
            density="compact"
            variant="text"
            confirm-text="Delete"
            title-text="Delete reading list"
            :text="`Delete ${item.name}? A list from story arc tags comes back on the next import. No comic file changes.`"
            @confirm="bulk('delete', [item.pk])"
          />
        </span>
      </template>
    </AdminTable>

    <AddListsDialog v-model="showAdd" :into="addInto" @imported="loadAll" />
    <ReviewDialog
      v-if="reviewList"
      v-model="showReview"
      :reading-list="reviewList"
      :initial-filter="reviewFilter"
      @changed="loadTable"
    />
    <SourcesDialog
      v-if="sourcesList"
      v-model="showSources"
      :reading-list="sourcesList"
      @add-source="openAdd"
      @changed="loadTable"
    />
    <DetailsDialog
      v-if="detailsList"
      v-model="showDetails"
      :reading-list="detailsList"
    />
    <CombineDialog
      v-model="showCombine"
      :pks="combinePks"
      @combined="onCombined"
    />
    <ConfirmDialog
      v-model="showWrite"
      confirm-text="Write"
      title-text="Write to comic files"
      :text="writeText"
      @confirm="
        bulk(
          'write',
          writeLists.map((list) => list.pk),
        )
      "
    />
  </div>
</template>

<script>
import {
  mdiDotsVertical,
  mdiFormatListChecks,
  mdiPlaylistPlus,
  mdiSourceBranch,
  mdiTrashCanOutline,
} from "@mdi/js";
import { mapActions, mapState } from "pinia";

import AdminSection from "@/components/admin/tabs/admin-section.vue";
import AdminTable from "@/components/admin/tabs/admin-table.vue";
import DateTimeColumn from "@/components/admin/tabs/datetime-column.vue";
import StatusListItem from "@/components/admin/drawer/status-list-item.vue";
import AdminExpandToggle from "@/components/admin/tabs/expand-toggle.vue";
import AddListsDialog from "@/components/admin/tabs/reading-lists/add-lists-dialog.vue";
import CombineDialog from "@/components/admin/tabs/reading-lists/combine-dialog.vue";
import DetailsDialog from "@/components/admin/tabs/reading-lists/details-dialog.vue";
import ReviewDialog from "@/components/admin/tabs/reading-lists/review-dialog.vue";
import SourcesDialog from "@/components/admin/tabs/reading-lists/sources-dialog.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useNowTimer } from "@/components/admin/use-now-timer";
import ReadingListExportMenu from "@/components/reading-list-export-menu.vue";
import { useAdminStore } from "@/stores/admin";
import {
  listTypeLabel,
  SOURCE_KINDS,
  useReadingListsStore,
} from "@/stores/reading-lists";

// The Source row for lists with no source, made by hand or of items only.
const NO_SOURCE = "none";
// The Visibility row for global lists: a colon is in no username.
const GLOBAL_OWNER = ":global";
const ownerOf = (list) => list.owner ?? GLOBAL_OWNER;
// Checklist rows: those with lists, then any ticked, so it can be unticked.
const checklistItems = (names, counts, ticked) =>
  Object.entries(names)
    .filter(([value]) => counts[value] || ticked.has(value))
    .map(([value, name]) => ({
      value,
      name,
      title: `${name} (${counts[value] ?? 0})`,
    }));

const HEADERS = Object.freeze([
  { title: "Name", key: "name" },
  { title: "Sources", key: "sources", sortable: false },
  { title: "In Library", key: "coverage", value: "matched" },
  { title: "Needs Review", key: "needsReview" },
  { title: "Visibility", key: "owner" },
  { title: "Updated", key: "updatedAt" },
  { title: "Actions", key: "actions", sortable: false },
]);
const WRITE_NONE_HINT =
  "Only global lists with issues in your library are written to files.";
// The librarian jobs of reading lists: sync, fetch, import, match.
const LIST_STATUS_TYPES = new Set(["RLS", "RLF", "RLI", "RLM"]);

export default {
  name: "AdminReadingListsTab",
  components: {
    AddListsDialog,
    AdminExpandToggle,
    AdminSection,
    AdminTable,
    CombineDialog,
    ConfirmDialog,
    DateTimeColumn,
    DetailsDialog,
    ReadingListExportMenu,
    ReviewDialog,
    SourcesDialog,
    StatusListItem,
  },
  setup() {
    const { now } = useNowTimer();
    return { now };
  },
  data() {
    return {
      mdiDotsVertical,
      mdiFormatListChecks,
      mdiPlaylistPlus,
      mdiSourceBranch,
      mdiTrashCanOutline,
      headers: HEADERS,
      search: "",
      // The source kinds and the owners ticked; none is every list.
      kindFilter: [],
      ownerFilter: [],
      missingOnly: false,
      reviewOnly: false,
      showMappings: false,
      showDetails: false,
      detailsList: null,
      selected: [],
      showSuggestions: false,
      showErrors: false,
      showAdd: false,
      addInto: null,
      showReview: false,
      reviewList: null,
      reviewFilter: "all",
      showSources: false,
      sourcesList: null,
      showCombine: false,
      combinePks: [],
      showWrite: false,
      writeLists: [],
      WRITE_NONE_HINT,
      COMBINE_TWO_HINT: "Select at least two lists to combine them.",
    };
  },
  computed: {
    ...mapState(useReadingListsStore, [
      "lists",
      "listsLoaded",
      "errorCount",
      "errors",
      "suggestions",
      "mappings",
    ]),
    ...mapState(useAdminStore, {
      listStatuses: (state) =>
        state.activeLibrarianStatuses.filter((status) =>
          LIST_STATUS_TYPES.has(status.statusType),
        ),
    }),
    kindCounts() {
      // How many lists have a source of each kind, or none.
      const counts = {};
      for (const list of this.lists) {
        const kinds = new Set(list.sources.map(({ kind }) => kind));
        if (!kinds.size) kinds.add(NO_SOURCE);
        for (const kind of kinds) {
          counts[kind] = (counts[kind] ?? 0) + 1;
        }
      }
      return counts;
    },
    kindItems() {
      const names = { [NO_SOURCE]: "None", ...SOURCE_KINDS };
      return checklistItems(names, this.kindCounts, new Set(this.kindFilter));
    },
    ownerCounts() {
      const counts = {};
      for (const list of this.lists) {
        const owner = ownerOf(list);
        counts[owner] = (counts[owner] ?? 0) + 1;
      }
      return counts;
    },
    ownerItems() {
      // Global first, then each owner by name.
      const ticked = new Set(this.ownerFilter);
      const owners = new Set([...Object.keys(this.ownerCounts), ...ticked]);
      owners.delete(GLOBAL_OWNER);
      const names = { [GLOBAL_OWNER]: "Global" };
      for (const owner of [...owners].sort()) {
        names[owner] = owner;
      }
      return checklistItems(names, this.ownerCounts, ticked);
    },
    noDataText() {
      // Say why the table is empty: no lists, or the filters hide them.
      return this.lists.length
        ? "No lists match these filters."
        : "No reading lists yet. Add lists, or tag comics with story arcs.";
    },
    mappingsLabel() {
      const count = this.mappings.length;
      return count === 1
        ? "1 saved series mapping"
        : `${count} saved series mappings`;
    },
    bulkHints() {
      const hints = [];
      if (this.selected.length < 2) hints.push(this.COMBINE_TWO_HINT);
      if (!this.selectedWritable.length) hints.push(this.WRITE_NONE_HINT);
      return hints;
    },
    selectedWritable() {
      const selected = new Set(this.selected);
      return this.lists.filter(
        (list) => selected.has(list.pk) && this.isWritable(list),
      );
    },
    writeText() {
      const count = this.writeLists.length;
      const which = count === 1 ? this.writeLists[0].name : `${count} lists`;
      return (
        `Tag the comics of ${which} with ${count === 1 ? "its" : "their"} ` +
        "story arc, numbered in list order? This changes comic files, in " +
        "your default tag formats. Each comic keeps its other arcs and tag " +
        "formats. Comics in read-only libraries are skipped. Once imported " +
        "again, the arc joins the same list as its tags source."
      );
    },
    filteredLists() {
      const search = (this.search || "").toLowerCase();
      const kinds = new Set(this.kindFilter);
      const owners = new Set(this.ownerFilter);
      const hasKind = (list) =>
        list.sources.length
          ? list.sources.some((source) => kinds.has(source.kind))
          : kinds.has(NO_SOURCE);
      return this.lists.filter(
        (list) =>
          (!search || list.name.toLowerCase().includes(search)) &&
          (!kinds.size || hasKind(list)) &&
          (!owners.size || owners.has(ownerOf(list))) &&
          (!this.missingOnly || list.matched < list.total) &&
          (!this.reviewOnly || list.needsReview > 0),
      );
    },
  },
  watch: {
    showErrors(value) {
      if (value) this.loadErrors();
    },
    showMappings(value) {
      if (value) this.loadMappings();
    },
  },
  mounted() {
    this.loadAll();
  },
  methods: {
    listTypeLabel,
    ...mapActions(useReadingListsStore, [
      "loadLists",
      "loadSuggestions",
      "loadErrors",
      "clearErrors",
      "act",
      "copyToGlobal",
      "setPrivate",
      "loadTable",
      "loadMappings",
      "deleteMapping",
    ]),
    loadAll() {
      this.loadTable();
      this.loadMappings();
      useAdminStore().loadTable("ActiveLibrarianStatus");
    },
    openDetails(item) {
      this.detailsList = item;
      this.showDetails = true;
    },
    sourceLabel(source) {
      const label = SOURCE_KINDS[source.kind] || source.kind;
      return source.attribution
        ? `${label} · ${source.attribution.toUpperCase()}`
        : label;
    },
    isWritable(item) {
      return !item.owner && item.matched > 0;
    },
    writeHint(item) {
      if (item.owner) return "A personal list stays in Codex.";
      if (!item.matched) return "None of its issues are in your library.";
      return "Tags its comics with its story arc.";
    },
    confirmWrite(lists) {
      this.writeLists = lists;
      this.showWrite = true;
    },
    completeTitle(item) {
      const kind = item.completeFrom?.kind;
      return kind === "comicvine_arc"
        ? "Complete from Comic Vine"
        : "Complete from Metron";
    },
    async bulk(action, pks) {
      const store = useReadingListsStore();
      await store.bulk(action, pks || this.selected);
      if (action === "delete") this.selected = [];
    },
    openAdd(into) {
      this.addInto = into;
      this.showAdd = true;
    },
    openReview(item, filter) {
      this.reviewList = item;
      this.reviewFilter = filter;
      this.showReview = true;
    },
    openSources(item) {
      this.sourcesList = item;
      this.showSources = true;
    },
    openCombine(pks) {
      this.combinePks = [...pks];
      this.showCombine = true;
    },
    onCombined() {
      this.selected = [];
      this.loadAll();
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
@use "@/components/admin/tabs/design.scss" as *;

@layer codex-components {
  .filters,
  .bulkHint {
    flex-basis: 100%;
    margin-top: 0;
  }

  .bulkBar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: $space-2;
    margin-bottom: $space-2;
  }

  // Wrap rather than squeeze: three fields on a phone row left Name unreadable.
  .nameFilter,
  .checklistFilter {
    flex: 1 1 160px;
    min-width: 160px;
    max-width: 240px;
  }

  .checklistSelection {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .checklistMore {
    margin-left: $space-1;
    color: rgb(var(--v-theme-text-disabled));
  }

  .bulkCount,
  .listType,
  .coverageText,
  .none {
    color: rgb(var(--v-theme-text-disabled));
    font-size: $text-meta;
  }

  .nameCell {
    display: flex;
    flex-direction: column;
  }

  .sourceChip {
    margin: 2px;
  }

  .coverage {
    min-width: 96px;
  }

  .suggestionLine {
    margin-bottom: $space-2;
  }

  .suggestionRow,
  .errorRow,
  .mappingRow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $space-2;
    font-size: $text-small;
    margin-bottom: $space-1;
  }

  .mappingPublisher {
    color: rgb(var(--v-theme-text-secondary));
    margin-left: $space-1;
  }

  .errorCard,
  .suggestionCard,
  .progressCard,
  .mappingsCard {
    margin-bottom: $space-4;
  }
}
</style>
