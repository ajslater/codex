<template>
  <div id="metadataBody">
    <section class="mdSection">
      <MetadataText :value="md.summary" :maxHeight="100" />
      <MetadataText :value="md.review" label="Review" :maxHeight="100" />
    </section>
    <MetadataTagsTable :tag-map="contributors" class="mdSection" />
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
    <v-table class="mdSection" v-if="showRatings">
      <tbody>
        <tr v-if="md.communityRating">
          <td class="key">Community Rating</td>
          <td>
            <MetadataText :value="md.communityRating" />
          </td>
        </tr>
        <tr v-if="md.criticalRating">
          <td class="key">Critical Rating</td>
          <td>
            <MetadataText :value="md.criticalRating" />
          </td>
        </tr>
        <tr v-if="md.ageRating">
          <td class="key">Age Rating</td>
          <td>
            <MetadataText :value="md.ageRating" />
          </td>
        </tr>
      </tbody>
    </v-table>
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
import { mapActions, mapGetters, mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import MetadataTags from "@/components/metadata/metadata-tags.vue";
import MetadataText from "@/components/metadata/metadata-text.vue";
import MetadataTagsTable from "@/components/metadata/tags-table.vue";
import { getDateTime } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

export default {
  name: "MetadataBody",
  components: {
    MetadataTagsTable,
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
  },
  computed: {
    ...mapGetters(useMetadataStore, ["contributors", "ratings", "tags"]),
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
    sizeLabel() {
      return this?.md?.group === "c" ? "Size" : "Total Size";
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
    showRatings() {
      return (
        this.md.communityRating || this.md.criticRating || this.md.ageRating
      );
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
@use "./table";

.inlineRow>* {
  display: inline-flex;
}

.mdSection {
  margin-top: 25px;
  background-color: rgb(var(--v-theme-surface));
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
