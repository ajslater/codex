<template>
  <v-dialog v-model="dialog" fullscreen transition="dialog-bottom-transition">
    <template #activator="{ props }">
      <v-btn
        aria-label="tags"
        class="tagButton cardControlButton"
        icon
        title="Tags"
        variant="text"
        v-bind="props"
        @click.prevent
      >
        <v-icon>
          {{ mdiTagOutline }}
        </v-icon>
      </v-btn>
    </template>
    <div v-if="md" id="metadataContainer" @keyup.esc="dialog = false">
      <header id="metadataHeader">
        <CloseButton
          class="closeButton"
          title="Close Metadata (esc)"
          size="x-large"
          @click="dialog = false"
        />
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
            :cover-pk="md.coverPk"
            :group="group"
            :child-count="md.childCount"
            :finished="md.finished"
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
        <div class="inlineRow">
          <MetadataText
            id="publisher"
            :value="md.publisher"
            group="p"
            label="Publisher"
            :obj="{ pk: md.id, group: md.group }"
          />
          <MetadataText
            id="imprint"
            :value="md.imprint"
            group="i"
            label="Imprint"
            :obj="{ pk: md.id, group: md.group }"
          />
        </div>
        <div class="inlineRow">
          <MetadataText
            id="series"
            :value="md.series"
            label="Series"
            group="s"
            :obj="{ pk: md.id, group: md.group }"
          />
        </div>
        <div class="inlineRow">
          <MetadataText
            id="volume"
            :value="md.volume"
            label="Volume"
            group="v"
            :obj="{ pk: md.id, group: md.group }"
          />
          <MetadataText :value="md.seriesVolumeCount" label="Volume Count" />
          <MetadataText
            id="issue"
            :value="formattedIssue"
            label="Issue"
            group="c"
            :obj="{ pk: md.id, group: md.group }"
          />
          <MetadataText :value="md.volumeIssueCount" label="Issue Count" />
          <MetadataText :value="md.name" label="Title" />
        </div>
        <div v-if="md.year || md.month || md.day" class="inlineRow">
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
        <section class="mdSection">
          <div class="quintRow">
            <MetadataText :value="pages" label="Pages" />
            <MetadataText
              label="Finished"
              :value="Boolean(md.finished).toString()"
            />
            <MetadataText
              label="Reading Direction"
              :value="readingDirectionText"
            />
            <MetadataText
              :value="Boolean(md.monochrome).toString()"
              label="Monochrome"
            />
            <MetadataText :value="md.original_format" label="Original Format" />
          </div>
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
          <MetadataText :value="md.summary" label="Summary" />
          <MetadataText :value="md.review" label="Review" />
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
        <section class="mdSection">
          <MetadataContributorsTable :value="md.contributors" />
        </section>
        <section class="mdSection inlineRow">
          <MetadataText :value="md.notes" label="Notes" />
        </section>
        <section class="inlineRow">
          <MetadataText :value="md.tagger" label="Tagger" />
          <MetadataText :value="md.scanInfo" label="Scan" />
        </section>
      </div>
      <footer id="footerLinks">
        <v-btn
          v-if="group === 'c'"
          id="downloadButton"
          title="Download Comic Archive"
          @click="download"
        >
          <v-icon v-if="group === 'c'">
            {{ mdiDownload }}
          </v-icon>
          Download
        </v-btn>
        <v-btn
          v-if="isReadButtonShown"
          :to="readerRoute"
          title="Read Comic"
          :disabled="!isReadButtonEnabled"
        >
          <v-icon>{{ readButtonIcon }}</v-icon>
          Read
        </v-btn>
        <span id="bottomRightButtons">
          <CloseButton
            class="closeButton"
            title="Close Metadata (esc)"
            size="x-large"
            @click="dialog = false"
          />
        </span>
      </footer>
    </div>
    <div v-else id="placeholderContainer">
      <CloseButton
        class="closeButton"
        title="Close Metadata (esc)"
        @click="dialog = false"
      />
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

import { getDownloadURL } from "@/api/v3/reader";
import { formattedIssue, getFullComicName } from "@/comic-name";
import BookCover from "@/components/book-cover.vue";
import CloseButton from "@/components/close-button.vue";
import MetadataContributorsTable from "@/components/metadata/contributors-table.vue";
import MetadataTags from "@/components/metadata/metadata-tags.vue";
import MetadataText from "@/components/metadata/metadata-text.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { getDateTime, NUMBER_FORMAT } from "@/datetime";
import { getReaderRoute } from "@/route";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
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
      twentyFourHourTime: (state) => state.settings.twentyFourHourTime,
      readingDirectionTitles: (state) => state.choices.static.readingDirection,
      identifierTypes: (state) => state.choices.static.identifierType,
      importMetadata: (state) => state.page.adminFlags.importMetadata,
    }),
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
      downloadFileName: (state) => {
        const md = state.md;
        return state.md?.filename
          ? md.filename
          : getFullComicName({
              seriesName: md.series.name,
              volumeName: md.volume.name,
              issueNumber: md.issueNumber,
              issueSuffix: md.issueSuffix,
            }) +
              "." +
              this.fileType.toLowerCase();
      },
    }),
    ...mapState(useBrowserStore, {
      q: (state) => state.settings.q,
    }),
    downloadURL() {
      return getDownloadURL(this.book);
    },
    isReadButtonShown() {
      return this.group === "c" && this.$route.name != "reader";
    },
    isReadButtonEnabled() {
      return this.$route.name === "browser" && Boolean(this.readerRoute);
    },
    readButtonIcon() {
      return this.isReadButtonEnabled ? mdiEye : mdiEyeOff;
    },
    readerRoute() {
      return getReaderRoute(this.md, this.importMetadata);
    },
    formattedIssue() {
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
      return this.readingDirectionTitles[this.md.readingDirection];
    },
    pages() {
      let pages = "";
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
      return this.md.size > 0 ? prettyBytes(this.md.size) : 0;
    },
    fileType() {
      return this.md.fileType || "Unknown";
    },
    titledIdentifiers() {
      if (!this.md.identifiers) {
        return this.md.identifiers;
      }
      const titledIdentifiers = [];
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
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
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
    download() {
      this.downloadIOSPWAFix(this.downloadURL, this.md.filename);
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;

#metadataContainer {
  display: flex;
  flex-direction: column;
  max-width: 100vw;
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

.closeButton {
  float: right;
  margin-left: 5px;
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

#footerLinks {
  margin-top: 20px;
}

#downloadButton {
  margin-right: 10px;
}

#bottomRightButtons {
  float: right;
}

#metadataContainer,
#placeholderContainer {
  padding-top: calc(20px + env(safe-area-inset-top));
  padding-left: calc(20px + env(safe-area-inset-left));
  padding-right: calc(20px + env(safe-area-inset-right));
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

@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #metadataContainer {
    font-size: 12px;
  }
}
</style>
