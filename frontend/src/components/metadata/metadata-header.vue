<template>
  <header id="metadataHeader">
    <MetadataText
      v-if="q"
      id="search"
      :value="q"
      label="Search Query"
      :highlight="true"
    />
    <div id="metadataBookCoverWrapper">
      <BookCover
        id="bookCover"
        :group="group"
        :pks="md.ids"
        :child-count="md.childCount"
        :finished="md.finished"
        :mtime="md.mtime"
      />
      <v-progress-linear
        class="bookCoverProgress"
        :model-value="md.progress"
        rounded
        background-color="inherit"
        height="2"
        aria-label="% read"
      />
    </div>
    <div id="seriesRow" class="inlineRow" :class="seriesRowClasses">
      <MetadataText
        v-for="series of md.seriesList"
        id="series"
        :key="series.ids"
        :value="series"
        group="s"
        :obj="{ ids: md.ids, group: md.group }"
        :label="seriesLabel"
      />
      <MetadataText
        v-for="volume of md.volumeList"
        id="volume"
        :key="volume.ids"
        :value="volume"
        group="v"
        :obj="{ ids: md.ids, group: md.group }"
        :label="volumeLabel"
      />
      <MetadataText :value="md.seriesVolumeCount" class="subdued" prefix="of" />
      <MetadataText
        id="issue"
        :value="formattedIssueNumber"
        group="c"
        :obj="{ ids: md.ids, group: md.group }"
      />
      <MetadataText :value="md.volumeIssueCount" class="subdued" prefix="/" />
    </div>
    <div id="titleRow" class="inlineRow">
      <MetadataText :value="md.name" />
    </div>
    <div id="publisherRow" class="inlineRow">
      <MetadataText
        v-for="publisher of md.publisherList"
        id="publisher"
        group="p"
        :key="publisher.ids"
        :label="publisherList"
        :obj="{ ids: md.ids, group: md.group }"
        :value="publisher"
      />
      <MetadataText
        v-for="imprint of md.imprintList"
        id="imprint"
        group="i"
        :key="imprint.ids"
        :label="imprintList"
        :obj="{ ids: md.ids, group: md.group }"
        :value="imprint"
      />
    </div>
    <div
      v-if="pages || md.year || md.month || md.day"
      class="inlineRow"
      id="pageDateRow"
    >
      <MetadataText :value="pages" />
      <MetadataText :value="md.year" class="datePicker" type="number" />
      <MetadataText :value="month" class="datePicker" />
      <MetadataText :value="md.day" class="datePicker" />
    </div>
    <MetadataControls :group="group" />
  </header>
</template>

<script>
import { mapActions, mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import { formattedIssue } from "@/comic-name";
import BookCover from "@/components/book-cover.vue";
import MetadataControls from "@/components/metadata/metadata-controls.vue";
import MetadataText from "@/components/metadata/metadata-text.vue";
import { NUMBER_FORMAT } from "@/datetime";
import { getReaderRoute } from "@/route";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

const SERIES_ROW_LARGE_LIMIT = 4;

export default {
  name: "MetadataHeader",
  components: {
    BookCover,
    MetadataControls,
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
    seriesRowClasses() {
      let count = 0;
      for (const key of ["seriesList", "volumeList"]) {
        count += this.md[key]?.length || 0;
      }
      return { shortSeriesRow: count <= SERIES_ROW_LARGE_LIMIT };
    },
    seriesLabel() {
      return this.md?.seriesList?.length > 1 ? "Series" : "";
    },
    volumeLabel() {
      return this.md?.volumeList?.length > 1 ? "Volume" : "";
    },
    publisherLabel() {
      return this.md?.publihserList?.length > 1 ? "Publisher" : "";
    },
    imprintLabel() {
      return this.md?.imprintList?.length > 1 ? "Imprint" : "";
    },
    month() {
      if (!this.md.month) {
        return "";
      }
      const date = new Date(1970, this.md.month, 1);
      return date.toLocaleString("default", { month: "long" });
    },
    readerRoute() {
      if (this.md?.ids) {
        return getReaderRoute(this.md, this.importMetadata);
      } else {
        return {};
      }
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
        pages += `Read ${humanBookmark} of `;
      }
      const humanPages = NUMBER_FORMAT.format(this.md.pageCount);
      pages += `${humanPages} page`;
      if (this.md.pageCount !== 1) {
        pages += "s";
      }
      if (this.md.progress > 0) {
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
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

.subdued {
  color: rgb(var(--v-theme-textDisabled))
}

#search {
  margin-bottom: 10px;
}

#metadataHeader {
  height: fit-content;
  max-width: 100vw;
}

#metadataBookCoverWrapper {
  float: left;
  position: relative;
  padding-top: 0px !important;
  margin-right: 15px;
}

#bookCover {
  position: relative;
}

.bookCoverProgress {
  margin-top: 1px;
}

#bookCover {
  padding-top: 0px !important;
}

.inlineRow>* {
  display: inline-flex;
}

.shortSeriesRow {
  min-height: 93px;
  margin-top: -24px;
  font-size: xx-large;
}

#titleRow {
  font-size: large;
  margin-top: -16px;
  min-height: 56.5px
}

#publisherRow {
  min-height: 62px
}

#pageDateRow {
  font-size: smaller;
  min-height: 44.5px
}
</style>
