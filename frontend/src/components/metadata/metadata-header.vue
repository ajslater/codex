<template>
  <header id="metadataHeader">
    <MetadataText
      v-if="q"
      id="search"
      :value="q"
      label="Search Query"
      :highlight="true"
    />
    <MetadataBookCover id="metadataBookCover" :group="group" />
    <section v-if="md.seriesList?.length === 1" id="seriesHeader">
      <div id="seriesRow" class="inlineRow">
        <MetadataText
          id="series"
          :key="md.seriesList[0].ids"
          :value="md.seriesList[0]"
          group="s"
          :highlight="'s' === md.group"
        />
        <MetadataText
          v-if="md.volumeList?.length === 1"
          id="volume"
          :key="md.volumeList[0].ids"
          :value="md.volumeList[0]"
          group="v"
          :highlight="'v' === md.group"
        />
        <MetadataText :value="seriesVolumeCount" class="subdued" />
        <MetadataText
          id="issue"
          :value="formattedIssueNumber"
          group="c"
          :highlight="'c' === md.group"
        />
        <MetadataText :value="volumeIssueCount" class="subdued" />
      </div>
    </section>
    <span v-if="md.name" id="titleRow">
      {{ collectionTitle }} {{ md.name }}
    </span>
    <MetadataTags
      v-if="md.seriesList?.length > 1"
      id="seriesTags"
      class="groupTags"
      label="Series"
      :values="md.seriesList"
      filter="s"
    />
    <div>
      <MetadataTags
        v-if="md.volumeList?.length > 1"
        id="volumeTags"
        class="groupTags"
        label="Volumes"
        :values="md.volumeList"
        filter="v"
      />
    </div>
    <div
      v-if="md.publisherList?.length === 1"
      id="publisherRow"
      class="inlineRow"
    >
      <MetadataText
        id="publisher"
        :key="md.publisherList[0].ids"
        group="p"
        :highlight="'p' === md.group"
        :value="md.publisherList[0]"
      />
      <MetadataText
        v-if="md.imprintList?.length === 1"
        id="imprint"
        :key="md.imprintList[0].ids"
        group="i"
        :highlight="'i' === md.group"
        :value="md.imprintList[0]"
      />
    </div>
    <MetadataTags
      v-if="md.publisherList?.length > 1"
      id="publisherTags"
      class="groupTags"
      label="Publishers"
      :values="md.publisherList"
      filter="p"
    />
    <MetadataTags
      v-if="md.imprintList?.length > 1"
      id="imprintTags"
      class="groupTags"
      label="Imprints"
      :values="md.imprintList"
      filter="i"
    />
    <div
      v-if="pages || md.year || md.month || md.day"
      id="pageDateRow"
      class="inlineRow"
    >
      <MetadataText :value="pages" />
      <MetadataText :value="date" class="datePicker" />
    </div>
  </header>
  <MetadataControls id="controls" :group="group" />
</template>

<script>
import { mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import { formattedIssue } from "@/comic-name";
import MetadataControls from "@/components/metadata/metadata-controls.vue";
import MetadataBookCover from "@/components/metadata/metadata-cover.vue";
import MetadataTags from "@/components/metadata/metadata-tags.vue";
import MetadataText from "@/components/metadata/metadata-text.vue";
import { NUMBER_FORMAT } from "@/datetime";
import { getReaderRoute } from "@/route";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

export default {
  name: "MetadataHeader",
  components: {
    MetadataBookCover,
    MetadataControls,
    MetadataTags,
    MetadataText,
  },
  props: {
    group: {
      type: String,
      required: true,
    },
  },
  computed: {
    ...mapState(useBrowserStore, {
      importMetadata: (state) => state.page?.adminFlags?.importMetadata,
      q: (state) => state.settings.q,
    }),
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
    }),
    collectionTitle() {
      if (this.md.collectionTitle) {
        return `${this.md.collectionTitle}:`;
      }
    },
    date() {
      if (!this.md.year && !this.md.month && !this.md.day) {
        return "";
      }
      const date = new Date(
        this.md.year || 1970,
        this.md.month || 1,
        this.md.day || 1,
      );
      const options = {};
      if (this.md.year) {
        options.year = "numeric";
      }
      if (this.md.month) {
        options.month = this.$vuetify.display.smAndDown ? "short" : "long";
      }
      if (this.md.day) {
        options.day = "numeric";
      }
      return date.toLocaleDateString("default", options);
    },
    readerRoute() {
      return this.md?.ids ? getReaderRoute(this.md, this.importMetadata) : {};
    },
    formattedIssueNumber() {
      if (!this.md) {
        return "Unknown";
      }
      if (
        (this.md.issueNumber === null || this.md.issueNumber === undefined) &&
        !this.md.issueSuffix
      ) {
        // comic-name.formattedIssue() shows 0 for null issue.
        return;
      }
      return "#" + formattedIssue(this.md);
    },
    pages() {
      let pages = "";
      if (!this.md) {
        return pages;
      }
      if (this.md.page) {
        const humanBookmark = NUMBER_FORMAT.format(this.md.page);
        pages += this.$vuetify.display.smAndDown
          ? `${humanBookmark} / `
          : `Read ${humanBookmark} of `;
      }
      const humanPages = NUMBER_FORMAT.format(this.md.pageCount);
      pages += `${humanPages} page`;
      if (this.md.pageCount !== 1) {
        pages += "s";
      }
      if (this.$vuetify.display.smAndUp && this.md.progress > 0) {
        pages += ` (${Math.round(this.md.progress)}%)`;
      }
      return pages;
    },
    size() {
      return this?.md?.size > 0 ? prettyBytes(this.md.size) : 0;
    },
    fileType() {
      return this?.md?.fileType || "Unknown";
    },
    seriesVolumeCount() {
      const count = this.md.seriesVolumeCount;
      return count ? `of ${count}` : "";
    },
    volumeIssueCount() {
      const count = this.md.volumeIssueCount;
      return count ? `/ ${count}` : "";
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

#metadataHeader {
  height: fit-content;
  max-width: 100vw;
}

#search {
  width: 100%;
  margin-bottom: 10px;
}

#metadataBookCover {
  float: left;
  margin-right: 15px;
}

.inlineRow,
.inlineRow > * {
  display: inline-flex;
}

#seriesRow {
  margin-top: -10px;
  font-size: xx-large;
}

#seriesRow :deep(.text:first-child),
#publisherRow :deep(.text:first-child),
#pageDateRow :deep(.text:first-child) {
  padding-left: 0px;
}

#seriesRow * {
  padding-top: 0px;
}

#titleRow {
  font-size: large;
}

.subdued {
  color: rgb(var(--v-theme-textDisabled));
}

#pageDateRow {
  display: block;
  font-size: smaller;
}

#controls {
  margin-top: 16px;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #metadataBookCover {
    margin-right: 10px;
  }

  #seriesRow {
    margin-top: 0px;
    font-size: large;
  }

  #titleRow {
    font-size: x-small;
  }
}
</style>
