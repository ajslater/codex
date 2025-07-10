<template>
  <div id="metadataBody">
    <section class="mdSection">
      <MetadataText :value="md.summary" :max-height="100" />
      <MetadataText :value="md.review" label="Review" :max-height="100" />
    </section>
    <MetadataTagsTable
      :key-map="roleMap"
      :tag-map="credits"
      class="mdSection"
    />
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
        <MetadataText :value="size" :label="sizeLabel" />
        <MetadataText :value="fileType" label="File Type" />
      </div>
      <div class="thirdRow">
        <MetadataText label="Reading Direction" :value="readingDirectionText" />
        <MetadataText
          :value="md.originalFormat?.name"
          label="Original Format"
        />
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
    <section v-if="md?.country || md?.language" class="halfRow mdSection">
      <MetadataText :value="md.country?.name" label="Country" />
      <MetadataText :value="md.language?.name" label="Language" />
    </section>
    <MetadataRatings class="mdSection" />
    <MetadataTagsTable :tag-map="tags" class="mdSection" />
    <section class="mdSection">
      <section class="inlineRow">
        <MetadataText :value="md.notes" label="Notes" />
      </section>
      <section class="inlineRow">
        <MetadataText :value="md.tagger" label="Tagger" />
        <MetadataText :value="md.scanInfo" label="Scan" />
      </section>
    </section>
  </div>
</template>

<script>
import { mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import MetadataRatings from "@/components/metadata/metadata-ratings.vue";
import MetadataText from "@/components/metadata/metadata-text.vue";
import MetadataTagsTable from "@/components/metadata/tags-table.vue";
import { getDateTime } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

export default {
  name: "MetadataBody",
  components: {
    MetadataRatings,
    MetadataTagsTable,
    MetadataText,
  },
  props: {
    book: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapState(useMetadataStore, ["credits", "ratings", "tags"]),
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings?.twentyFourHourTime,
      readingDirectionTitles: (state) => state.choices.static.readingDirection,
    }),
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
      roleMap: (state) => state.roleMap,
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
    sizeLabel() {
      return this?.md?.group === "c" ? "Size" : "Total Size";
    },
    fileType() {
      return this?.md?.fileType || "Unknown";
    },
  },
  methods: {
    formatDateTime(ds) {
      return getDateTime(ds, this.twentyFourHourTime);
    },
  },
};
</script>

<style scoped lang="scss">
@use "./table";

.inlineRow > * {
  display: inline-flex;
}

.mdSection {
  margin-top: 25px;
  background-color: rgb(var(--v-theme-surface));
}

.halfRow > * {
  width: 50%;
  display: inline-flex;
}

.thirdRow > * {
  width: 33.333%;
  display: inline-flex;
}

.quarterRow > * {
  width: 25%;
  display: inline-flex;
}
</style>
