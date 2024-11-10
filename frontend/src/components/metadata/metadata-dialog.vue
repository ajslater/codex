<template>
  <v-dialog v-model="dialog" fullscreen transition="dialog-bottom-transition">
    <template #activator="{ props }">
      <v-btn
        aria-label="tags"
        class="tagButton cardControlButton"
        :variant="buttonVariant"
        :icon="mdiTagOutline"
        title="Tags"
        v-bind="props"
        @click.prevent
      />
    </template>
    <CloseButton
      class="closeButton"
      title="Close Metadata (esc)"
      @click="dialog = false"
    />
    <div
      v-if="showContainer"
      id="metadataContainer"
      @keyup.esc="dialog = false"
    >
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
        <div id="seriesRow" class="inlineRow">
          <MetadataText
            v-for="series of md.seriesList"
            id="series"
            :key="series.ids"
            :value="series"
            label="Series"
            group="s"
            :obj="{ ids: md.ids, group: md.group }"
          />
          <MetadataText
            v-for="volume of md.volumeList"
            id="volume"
            :key="volume.ids"
            :value="volume"
            label="Volume"
            group="v"
            :obj="{ ids: md.ids, group: md.group }"
          />
          <MetadataText :value="md.seriesVolumeCount" label="Volume Count" />
          <MetadataText
            id="issue"
            :value="formattedIssue"
            label="Issue"
            group="c"
            :obj="{ ids: md.ids, group: md.group }"
          />
          <MetadataText :value="md.volumeIssueCount" label="Issue Count" />
        </div>
        <div id="issueRow" class="inlineRow">
          <MetadataText :value="md.name" label="Title" />
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

        <div v-if="pages || md.year || md.month || md.day" class="inlineRow">
          <MetadataText :value="pages" label="Pages" />
          <MetadataText
            :value="md.year"
            label="Year"
            class="datePicker"
            type="number"
          />
          <MetadataText :value="md.month" label="Month" class="datePicker" />
          <MetadataText :value="md.day" label="Day" class="datePicker" />
        </div>
      </header>
      <div id="metadataBody">
        <section id="controls">
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

        <section class="mdSection">
          <MetadataText :value="md.summary" label="Summary" />
          <MetadataText :value="md.review" label="Review" />
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
            <MetadataText
              label="Reading Direction"
              :value="readingDirectionText"
            />
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
    </div>
    <div v-else id="placeholderContainer">
      <div id="placeholderTitle">Tags Loading</div>
      <PlaceholderLoading
        :model-value="progress"
        :indeterminate="progress >= 100"
        class="placeholder"
      />
    </div>
  </v-dialog>
</template>

<script>
import { mdiDownload, mdiEye, mdiEyeOff, mdiTagOutline } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import { formattedIssue } from "@/comic-name";
import BookCover from "@/components/book-cover.vue";
import CloseButton from "@/components/close-button.vue";
import DownloadButton from "@/components/download-button.vue";
import MarkReadButton from "@/components/mark-read-button.vue";
import MetadataContributorsTable from "@/components/metadata/contributors-table.vue";
import MetadataTags from "@/components/metadata/metadata-tags.vue";
import MetadataText from "@/components/metadata/metadata-text.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { getDateTime, NUMBER_FORMAT } from "@/datetime";
import { getReaderRoute } from "@/route";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

// Progress circle
// Can take 19 seconds for 22k children on huge collections
const CHILDREN_PER_SECOND = 1160;
const MIN_SECS = 0.05;
const UPDATE_INTERVAL = 250;

export default {
  name: "MetadataButton",
  components: {
    BookCover,
    CloseButton,
    DownloadButton,
    MarkReadButton,
    MetadataContributorsTable,
    MetadataTags,
    MetadataText,
    PlaceholderLoading,
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
    toolbar: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      mdiDownload,
      mdiTagOutline,
      dialog: false,
      progress: 0,
    };
  },
  computed: {
    ...mapGetters(useAuthStore, ["isUserAdmin"]),
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings?.twentyFourHourTime,
      readingDirectionTitles: (state) => state.choices.static.readingDirection,
      identifierTypes: (state) => state.choices.static.identifierType,
      importMetadata: (state) => state.page?.adminFlags?.importMetadata,
      q: (state) => state.settings.q,
    }),
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
    }),
    showContainer() {
      return this.md?.loaded || false;
    },
    buttonVariant() {
      return this.toolbar ? "plain" : "text";
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
    formattedIssue() {
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
      return formattedIssue(this.md);
    },
    readingDirectionText() {
      if (!this.md) {
        return "Unknown";
      }
      return this.readingDirectionTitles[this.md.readingDirection];
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
      pages += `${humanPages} pages`;
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
    multiGroup() {
      return this.md?.ids ? this.md.ids.length > 1 : false;
    },
  },
  watch: {
    dialog(to) {
      if (to) {
        this.dialogOpened();
      } else {
        this.clearMetadata();
      }
    },
  },
  methods: {
    ...mapActions(useMetadataStore, ["clearMetadata", "loadMetadata"]),
    ...mapActions(useBrowserStore, ["identifierTypeTitle"]),
    dialogOpened() {
      const pks = this.book.ids ? this.book.ids : [this.book.pk];
      const data = {
        group: this.group,
        pks,
      };
      this.loadMetadata(data);
      this.startProgress();
    },
    startProgress() {
      this.startTime = Date.now();
      this.estimatedMS =
        Math.max(MIN_SECS, this.children / CHILDREN_PER_SECOND) * 1000;
      this.updateProgress();
    },
    updateProgress() {
      const elapsed = Date.now() - this.startTime;
      this.progress = (elapsed / this.estimatedMS) * 100;
      if (this.progress >= 100 || this.md) {
        return;
      }
      setTimeout(() => {
        this.updateProgress();
      }, UPDATE_INTERVAL);
    },
    formatDateTime(ds) {
      return getDateTime(ds, this.twentyFourHourTime);
    },
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

.closeButton {
  position: fixed;
  top: 20px;
  right: 20px;
}

#metadataContainer {
  display: flex;
  flex-direction: column;
  max-width: 100vw;
  overflow-y: auto !important;
}

#search {
  margin-bottom: 10px;
}

#metadataHeader {
  height: fit-content;
  max-width: 100vw;
}

#placeholderContainer {
  min-height: 100%;
  min-width: 100%;
  text-align: center;
}

#placeholderTitle {
  font-size: xx-large;
  color: rgb(var(--v-theme-textDisabled));
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

.mdSection {
  margin-top: 25px;
}

#seriesRow {
  font-size: x-large;
}

#issueRow {
  font-size: large;
}

#controls {
  padding-top: 20px;
}

.controlButton {
  margin-right: 10px;
}

#metadataContainer,
#placeholderContainer {
  padding-top: max(20px, env(safe-area-inset-top));
  padding-left: max(20px, env(safe-area-inset-left));
  padding-right: max(20px, env(safe-area-inset-right));
  padding-bottom: max(20px, env(safe-area-inset-bottom));
}

.placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.headerHalfRow>* {
  width: calc((100vw - 175px) / 2);
  display: inline-flex;
}

.headerQuarterRow>* {
  width: calc((100vw - 175px) / 4);
  display: inline-flex;
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

.quintRow>* {
  width: 20%;
  display: inline-flex;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #metadataContainer {
    font-size: 12px;
  }
}
</style>
