<template>
  <section v-if="details" class="mdSection readingListDetails">
    <div class="detailsHeadline">
      <span v-if="typeLabel" class="detailsType">{{ typeLabel }}</span>
      <span v-if="years" class="detailsYears">{{ years }}</span>
      <span v-if="details.personal" class="detailsPersonal">Your list</span>
    </div>
    <p class="detailsCoverage">{{ coverage }}</p>
    <MetadataText :value="details.description" :max-height="100" />
    <table class="detailsTable">
      <tbody>
        <tr v-if="details.sources.length">
          <td class="key">Sources</td>
          <td>
            <span
              v-for="(source, index) in details.sources"
              :key="index"
              class="detailsSource"
            >
              {{ source.label }}
              <template v-if="source.attribution">
                ·
                <a
                  v-if="source.attributionUrl"
                  :href="source.attributionUrl"
                  target="_blank"
                  rel="noreferrer noopener"
                  >{{ source.attribution.toUpperCase() }}</a
                >
                <span v-else>{{ source.attribution.toUpperCase() }}</span>
              </template>
            </span>
          </td>
        </tr>
        <tr v-for="neighbour in neighbours" :key="neighbour.label">
          <td class="key">{{ neighbour.label }}</td>
          <td>
            <a
              v-if="neighbour.pk"
              href="#"
              @click.prevent="open(neighbour.pk)"
              >{{ neighbour.name }}</a
            >
            <span v-else>{{ neighbour.name }} (not in the library)</span>
          </td>
        </tr>
      </tbody>
    </table>
    <div class="detailsActions">
      <v-btn
        variant="tonal"
        size="small"
        :disabled="!details.continue"
        :title="details.continue ? '' : CONTINUE_DONE_HINT"
        @click="continueReading(details.pk)"
      >
        Continue Reading
      </v-btn>
      <v-menu>
        <template #activator="{ props }">
          <v-btn v-bind="props" variant="text" size="small">Export</v-btn>
        </template>
        <v-list density="compact">
          <ReadingListExportMenu :pk="details.pk" />
          <ReadingListExportMenu
            v-if="details.missing"
            :pk="details.pk"
            missing
          />
        </v-list>
      </v-menu>
    </div>
  </section>
</template>

<script>
import { mapActions, mapState } from "pinia";

import MetadataText from "@/components/metadata/metadata-text.vue";
import ReadingListExportMenu from "@/components/reading-list-export-menu.vue";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";
import { listTypeLabel, useReadingListsStore } from "@/stores/reading-lists";

const ARCS = "arcs";

/*
 * One reading list's own details, when the metadata dialog shows a list:
 * what it is, how much of it is here and read, where it came from, the
 * lists around it, Continue Reading and Export, Export Missing too.
 */
export default {
  name: "MetadataReadingListDetails",
  components: { MetadataText, ReadingListExportMenu },
  data() {
    return {
      CONTINUE_DONE_HINT:
        "Every issue of this list the library has is read. Mark one unread to read it again.",
    };
  },
  computed: {
    ...mapState(useMetadataStore, {
      details: (state) => state.md?.readingListDetails,
    }),
    typeLabel() {
      return listTypeLabel(this.details?.listType);
    },
    years() {
      const { startYear, endYear } = this.details || {};
      if (!startYear) return "";
      return endYear && endYear !== startYear
        ? `${startYear}–${endYear}`
        : String(startYear);
    },
    neighbours() {
      // The lists before and after this one: links when the library has them.
      const { previous, next } = this.details || {};
      return [
        previous && { ...previous, label: "Before" },
        next && { ...next, label: "After" },
      ].filter(Boolean);
    },
    coverage() {
      const { inLibrary, total, read } = this.details;
      return `${inLibrary} of ${total} in the library, ${read} read`;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["routeWithSettings"]),
    ...mapActions(useReadingListsStore, ["continueReading"]),
    open(pk) {
      const route = {
        name: "browser",
        params: { collection: ARCS, pks: String(pk), page: 1 },
      };
      this.routeWithSettings({ topCollection: ARCS }, route);
    },
  },
};
</script>

<style scoped lang="scss">
@use "./table";

@layer codex-components {
  .detailsHeadline {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    color: rgb(var(--v-theme-text-secondary));
  }

  .detailsType {
    font-weight: bold;
  }

  .detailsCoverage {
    margin: 4px 0;
  }

  .detailsSource + .detailsSource::before {
    content: " + ";
  }

  .detailsActions {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }
}
</style>
