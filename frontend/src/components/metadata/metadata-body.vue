<template>
  <div id="metadataBody">
    <section class="mdSection">
      <MetadataText :value="md.summary" label="Summary" :maxHeight="100" />
      <MetadataText :value="md.review" label="Review" :maxHeight="100" />
    </section>
    <section class="mdSection">
      <MetadataContributorsTable :value="md.contributors" />
    </section>
    <section class="mdSection">
      <div class="quarterRow">
        <MetadataText
          v-if="md.createdAt"
          :value="formatDateTime(md.createdAt)"
          label="Created at"
          class="mtime"
        />
        <MetadataText
          v-if="md.updatedAt"
          :value="formatDateTime(md.updatedAt)"
          label="Updated at"
          class="mtime"
        />
        <MetadataText :value="size" label="Size" />
        <MetadataText :value="fileType" label="File Type" />
      </div>
      <div class="thirdRow">
        <MetadataText label="Reading Direction" :value="readingDirectionText" />
        <MetadataText :value="md.original_format" label="Original Format" />
        <MetadataText
          :value="Boolean(md.monochrome).toString()"
          label="Monochrome"
        />
      </div>
      <div class="lastSmallRow">
        <MetadataText
          group="f"
          :value="{ pk: md.parentFolderId, name: md.path }"
          label="Path"
        />
      </div>
    </section>
    <section class="halfRow mdSection">
      <MetadataText :value="md.country" label="Country" />
      <MetadataText :value="md.language" label="Language" />
    </section>
    <section class="mdSection">
      <MetadataTags :values="titledIdentifiers" label="Identifiers" />
    </section>
    <section class="mdSection">
      <MetadataText :value="md.communityRating" label="Community Rating" />
      <MetadataText :value="md.criticalRating" label="Critical Rating" />
      <MetadataText :value="md.ageRating" label="Age Rating" />
    </section>
    <section class="mdSection">
      <MetadataTags :values="md.genres" label="Genres" filter="genres" />
      <MetadataTags
        :values="md.characters"
        label="Characters"
        filter="characters"
      />
      <MetadataTags :values="md.teams" label="Teams" filter="teams" />
      <MetadataTags
        :values="md.locations"
        label="Locations"
        filter="locations"
      />
      <MetadataTags
        :values="md.seriesGroups"
        label="Series Groups"
        filter="seriesGroups"
      />
      <MetadataTags :values="md.stories" label="Stories" filter="stories" />
      <MetadataTags
        :values="md.storyArcNumbers"
        label="Story Arcs"
        filter="storyArcs"
      />
      <MetadataTags :values="md.tags" label="Tags" filter="tags" />
    </section>
    <section class="mdSection inlineRow">
      <MetadataText :value="md.notes" label="Notes" />
    </section>
    <section class="inlineRow">
      <MetadataText :value="md.tagger" label="Tagger" />
      <MetadataText :value="md.scanInfo" label="Scan" />
    </section>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import MetadataContributorsTable from "@/components/metadata/contributors-table.vue";
import MetadataTags from "@/components/metadata/metadata-tags.vue";
import MetadataText from "@/components/metadata/metadata-text.vue";
import { getDateTime } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

export default {
  name: "MetadataBody",
  components: {
    MetadataContributorsTable,
    MetadataTags,
    MetadataText,
  },
  props: {
    group: {
      type: String,
      required: true,
    },
    book: {
      type: Object,
      required: true,
    },
    children: {
      type: Number,
      default: 1,
    },
  },
  computed: {
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings?.twentyFourHourTime,
      readingDirectionTitles: (state) => state.choices.static.readingDirection,
      identifierTypes: (state) => state.choices.static.identifierType,
    }),
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
    }),
    readingDirectionText() {
      if (!this.md) {
        return "Unknown";
      }
      return this.readingDirectionTitles[this.md.readingDirection];
    },
    size() {
      return this?.md?.size > 0 ? prettyBytes(this.md.size) : 0;
    },
    fileType() {
      return this?.md?.fileType || "Unknown";
    },
    titledIdentifiers() {
      const titledIdentifiers = [];
      if (!this?.md?.identifiers) {
        return titledIdentifiers;
      }
      for (const identifier of this.md.identifiers) {
        const parts = identifier.name.split(":");
        const idType = parts[0];
        const code = parts[1];
        const finalTitle = this.identifierTypeTitle(idType);
        let name = "";
        if (finalTitle && finalTitle !== "None") {
          name += finalTitle + ":";
        }
        name += code;

        titledIdentifiers.push({ ...identifier, name });
      }
      return titledIdentifiers;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["identifierTypeTitle"]),
    formatDateTime(ds) {
      return getDateTime(ds, this.twentyFourHourTime);
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

.inlineRow>* {
  display: inline-flex;
}

.mdSection {
  margin-top: 25px;
}

.halfRow>* {
  width: 50%;
  display: inline-flex;
}

.thirdRow>* {
  width: 33.333%;
  display: inline-flex;
}

.quarterRow>* {
  width: 25%;
  display: inline-flex;
}
</style>
