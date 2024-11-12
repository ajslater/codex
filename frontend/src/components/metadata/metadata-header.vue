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
    <section id="seriesHeader" v-if="md.seriesList?.length === 1">
      <div id="seriesRow" class="inlineRow">
        <MetadataText
          id="series"
          :key="md.seriesList[0].ids"
          :value="md.seriesList[0]"
          group="s"
          :obj="{ ids: md.ids, group: md.group }"
        />
        <MetadataText
          v-if="md.volumeList?.length === 1"
          id="volume"
          :key="md.volumeList[0].ids"
          :value="md.volumeList[0]"
          group="v"
          :obj="{ ids: md.ids, group: md.group }"
        />
        <MetadataText
          :value="md.seriesVolumeCount"
          class="subdued"
          prefix="of"
        />
        <MetadataText
          id="issue"
          :value="formattedIssueNumber"
          group="c"
          :obj="{ ids: md.ids, group: md.group }"
        />
        <MetadataText :value="md.volumeIssueCount" class="subdued" prefix="/" />
      </div>
    </section>
    <div id="titleRow" class="inlineRow" v-if="md.name">
      {{ md.name }}
    </div>
    <MetadataTags
      v-if="md.seriesList?.length > 1"
      id="seriesTags"
      label="Series"
      :values="md.seriesList"
      filter="s"
    />
    <MetadataTags
      v-if="md.volumeList?.length > 1"
      id="volumeTags"
      label="Volumes"
      :values="md.volumeList"
      filter="v"
    />
    <div
      id="publisherRow"
      class="inlineRow"
      v-if="md.publisherList?.length === 1"
    >
      <MetadataText
        id="publisher"
        group="p"
        :key="md.publisherList[0].ids"
        :obj="{ ids: md.ids, group: md.group }"
        :value="md.publisherList[0]"
      />
      <MetadataText
        v-if="md.imprintList?.length === 1"
        id="imprint"
        group="i"
        :key="md.imprintList[0].ids"
        :obj="{ ids: md.ids, group: md.group }"
        :value="md.imprintList[0]"
      />
    </div>
    <MetadataTags
      v-if="md.publisherList?.length > 1"
      id="publisherTags"
      label="Publishers"
      :values="md.publisherList"
      filter="p"
    />
    <MetadataTags
      v-if="md.imprintList?.length > 1"
      id="imprintTags"
      label="Imprints"
      :values="md.imprintList"
      filter="i"
    />
    <div
      v-if="pages || md.year || md.month || md.day"
      class="inlineRow"
      id="pageDateRow"
    >
      <MetadataText :value="pages" />
      <MetadataText :value="date" class="datePicker" />
    </div>
  </header>
  <MetadataControls id="controls" :group="group" />
</template>

<script>
import { mapActions, mapState } from "pinia";
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
    date() {
      if (!this.md.year && !this.md.month && !this.md.day) {
        return "";
      }
      if (this.md.year && this.md.month && this.md.day) {
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
      }
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
        if (this.$vuetify.display.smAndDown) {
          pages += `${humanBookmark} / `;
        } else {
          pages += `Read ${humanBookmark} of `;
        }
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
  margin-right: 10px;
}

#headerText {
  display: inline-flex;
  flex-direction: column;
}

.inlineRow>* {
  display: inline-flex;
}

#seriesTags,
#volumeTags,
#publisherTags,
#imprintTags {
  margin-left: 8px !important;
}

#seriesRow {
  margin-top: -10px;
  font-size: xx-large;
}

#seriesRow * {
  padding-top: 0px;
}

#titleRow {
  font-size: large;
  margin-left: 185px
}

.subdued {
  color: rgb(var(--v-theme-textDisabled))
}

#pageDateRow {
  font-size: smaller;
}

#controls {
  margin-top: 10px;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #metadataBookCover {
    margin-right: 10px;
  }

  #seriesRow {
    margin-top: 0px;
    font-size: small;
  }

  #titleRow {
    font-size: x-small;
    margin-left: 110px
  }
}
</style>
