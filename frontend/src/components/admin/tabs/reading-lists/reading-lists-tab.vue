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
      <v-select
        v-model="kindFilter"
        :items="kindItems"
        label="Source"
        density="compact"
        hide-details
        clearable
        class="kindFilter"
      />
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
        :title="
          selected.length < 2
            ? 'Select at least two lists to combine them.'
            : ''
        "
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
        :title="selectedWritable.length ? '' : WRITE_NONE_HINT"
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
    </div>

    <AdminTable
      v-model="selected"
      :headers="headers"
      :items="filteredLists"
      :loading="!listsLoaded"
      show-select
    >
      <template #no-data>
        <td class="adminNoData" colspan="100%">
          No reading lists yet. Add lists, or tag comics with story arcs.
        </td>
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
      @changed="loadLists"
    />
    <SourcesDialog
      v-if="sourcesList"
      v-model="showSources"
      :reading-list="sourcesList"
      @add-source="openAdd"
      @changed="loadLists"
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
import AdminExpandToggle from "@/components/admin/tabs/expand-toggle.vue";
import AddListsDialog from "@/components/admin/tabs/reading-lists/add-lists-dialog.vue";
import CombineDialog from "@/components/admin/tabs/reading-lists/combine-dialog.vue";
import ReviewDialog from "@/components/admin/tabs/reading-lists/review-dialog.vue";
import SourcesDialog from "@/components/admin/tabs/reading-lists/sources-dialog.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import ReadingListExportMenu from "@/components/reading-list-export-menu.vue";
import {
  listTypeLabel,
  SOURCE_KINDS,
  useReadingListsStore,
} from "@/stores/reading-lists";

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
const KIND_ITEMS = Object.freeze(
  Object.entries(SOURCE_KINDS).map(([value, title]) => ({ value, title })),
);

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
    ReadingListExportMenu,
    ReviewDialog,
    SourcesDialog,
  },
  data() {
    return {
      mdiDotsVertical,
      mdiFormatListChecks,
      mdiPlaylistPlus,
      mdiSourceBranch,
      mdiTrashCanOutline,
      headers: HEADERS,
      kindItems: KIND_ITEMS,
      search: "",
      kindFilter: null,
      missingOnly: false,
      reviewOnly: false,
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
    };
  },
  computed: {
    ...mapState(useReadingListsStore, [
      "lists",
      "listsLoaded",
      "errorCount",
      "errors",
      "suggestions",
    ]),
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
      return this.lists.filter(
        (list) =>
          (!search || list.name.toLowerCase().includes(search)) &&
          (!this.kindFilter ||
            list.sources.some((source) => source.kind === this.kindFilter)) &&
          (!this.missingOnly || list.matched < list.total) &&
          (!this.reviewOnly || list.needsReview > 0),
      );
    },
  },
  watch: {
    showErrors(value) {
      if (value) this.loadErrors();
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
    ]),
    loadAll() {
      this.loadLists();
      this.loadSuggestions();
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
  .bulkBar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: $space-2;
    margin-bottom: $space-2;
  }

  .nameFilter,
  .kindFilter {
    max-width: 240px;
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
  .errorRow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $space-2;
    font-size: $text-small;
    margin-bottom: $space-1;
  }

  .errorCard,
  .suggestionCard {
    margin-bottom: $space-4;
  }
}
</style>
