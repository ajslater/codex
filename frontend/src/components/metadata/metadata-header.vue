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
        :label="md.seriesList.length > 1 ? 'Series' : ''"
      />
      <MetadataText
        v-for="volume of md.volumeList"
        id="volume"
        :key="volume.ids"
        :value="volume"
        group="v"
        :obj="{ ids: md.ids, group: md.group }"
        :label="md.volumeList.length > 1 ? 'Volume' : ''"
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
        :key="publisher.ids"
        :value="publisher"
        group="p"
        label="Publisher"
        :obj="{ ids: md.ids, group: md.group }"
      />
      <MetadataText
        v-for="imprint of md.imprintList"
        id="imprint"
        :key="imprint.ids"
        :value="imprint"
        group="i"
        label="Imprint"
        :obj="{ ids: md.ids, group: md.group }"
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
    <section id="controls">
      <section id="controlRow">
        <DownloadButton
          id="downloadButton"
          class="controlButton"
          :button="true"
          :group="downloadGroup"
          :pks="downloadPks"
          :children="children"
          :names="downloadNames"
          :ts="md.mtime"
        />
        <MarkReadButton
          id="markReadButton"
          class="controlButton"
          :button="true"
          :item="markReadItem"
        />
        <v-btn
          v-if="isReadButtonShown"
          id="readButton"
          class="controlButton"
          :to="readerRoute"
          title="Read Comic"
          :disabled="!isReadButtonEnabled"
        >
          <v-icon>{{ readButtonIcon }}</v-icon>
          Read
        </v-btn>
      </section>
    </section>
  </header>
</template>

<script>
import { mdiDownload, mdiEye, mdiEyeOff, mdiTagOutline } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import { formattedIssue } from "@/comic-name";
import BookCover from "@/components/book-cover.vue";
import DownloadButton from "@/components/download-button.vue";
import MarkReadButton from "@/components/mark-read-button.vue";
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
    DownloadButton,
    MarkReadButton,
    MetadataText,
  },
  props: {
    group: {
      type: String,
      required: true,
    },
    children: {
      type: Number,
      default: 1,
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
      const count = this.md.seriesList.length + this.md.volumeList.length;
      return { shortSeriesRow: count <= SERIES_ROW_LARGE_LIMIT };
    },
    downloadGroup() {
      return this.md.group;
    },
    downloadPks() {
      return this.md.ids;
    },
    downloadNames() {
      const md = this.md;
      if (!md) {
        return ["Unknown.cbz"];
      } else if (md.fileName) {
        return [md.fileName];
      } else {
        return [
          this.firstNameFromList(md.publisherList),
          this.firstNameFromList(md.imprintList),
          this.firstNameFromList(md.seriesList),
          this.firstNameFromList(md.volumeList),
          this.md.name,
        ];
      }
    },
    isReadButtonShown() {
      return this.group === "c" && this.$route.name != "reader";
    },
    isReadButtonEnabled() {
      return Boolean(this.readerRoute);
    },
    markReadItem() {
      return {
        group: this.md.group,
        ids: this.md.ids,
        finished: this.md.finished,
        name: this.downloadNames,
        children: this.md.children,
      };
    },
    month() {
      if (!this.md.month) {
        return "";
      }
      const date = new Date(1970, this.md.month, 1);
      return date.toLocaleString("default", { month: "long" });
    },
    readButtonIcon() {
      return this.isReadButtonEnabled ? mdiEye : mdiEyeOff;
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
  methods: {
    firstNameFromList(list) {
      let name = "";
      if (list) {
        for (const obj of Object.values(list)) {
          if (obj.name) {
            name = obj.name;
            break;
          }
        }
      }
      return name;
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

#controls {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  margin-top: 4px;
}

.controlButton {
  margin-right: 10px;
}
</style>
