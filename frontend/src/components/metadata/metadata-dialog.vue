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
    <div v-if="md" id="metadataContainer">
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
        <div class="headerHalfRow">
          <MetadataText
            id="publisher"
            :value="md.publisher"
            label="Publisher"
            :highlight="'p' === md.group"
          />
          <MetadataText
            id="imprint"
            :value="md.imprint"
            label="Imprint"
            :highlight="'i' === md.group"
          />
        </div>
        <MetadataText
          id="series"
          :value="md.series"
          label="Series"
          :highlight="'s' === md.group"
        />
        <div class="headerQuarterRow">
          <MetadataText
            id="volume"
            :value="md.volume"
            label="Volume"
            :highlight="'v' === md.group"
          />
          <MetadataText :value="md.volumeCount" label="Volume Count" />
          <MetadataText
            id="issue"
            :value="formattedIssue"
            label="Issue"
            :highlight="'c' === md.group"
          />
          <MetadataText :value="md.issueCount" label="Issue Count" />
        </div>
        <section class="mdSection">
          <MetadataText :value="md.name" label="Title" />
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
          <MetadataText :value="md.format" label="Format" />
        </section>
      </header>
      <div id="metadataBody">
        <section class="mdSection">
          <div class="thirdRow">
            <MetadataText :value="pages" label="Pages" />
            <MetadataText :value="md.finished" label="Finished" />
            <MetadataText :value="ltrText" label="Reading Direction" />
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
            <MetadataText :value="fileFormat" label="File Type" />
          </div>
          <div class="lastSmallRow">
            <MetadataText :value="md.path" label="Path" />
          </div>
        </section>
        <section class="halfRow mdSection">
          <MetadataText :value="md.country" label="Country" />
          <MetadataText :value="md.language" label="Language" />
        </section>
        <section class="mdSection">
          <MetadataText :value="md.communityRating" label="Community Rating" />
          <MetadataText :value="md.criticalRating" label="Critical Rating" />
          <MetadataText :value="md.ageRating" label="Age Rating" />
        </section>
        <section class="mdSection">
          <MetadataTags :values="md.genres" label="Genres" />
          <MetadataTags :values="md.tags" label="Tags" />
          <MetadataTags :values="md.teams" label="Teams" />
          <MetadataTags :values="md.characters" label="Characters" />
          <MetadataTags :values="md.locations" label="Locations" />
          <MetadataTags :values="md.storyArcs" label="Story Arcs" />
          <MetadataTags :values="md.seriesGroups" label="Series Groups" />
        </section>
        <section class="mdSection">
          <MetadataText :value="md.web" label="Web Link" :link="true" />
          <MetadataText :value="md.summary" label="Summary" />
          <MetadataText :value="md.comments" label="Comments" />
          <MetadataText :value="md.notes" label="Notes" />
          <MetadataText :value="md.scanInfo" label="Scan" />
        </section>
        <section class="mdSection">
          <MetadataCreditsTable :value="md.credits" />
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
import humanize from "humanize";
import { mapActions, mapGetters, mapState } from "pinia";

import { getDownloadURL } from "@/api/v3/reader";
import { formattedIssue, getFullComicName } from "@/comic-name";
import BookCover from "@/components/book-cover.vue";
import CloseButton from "@/components/close-button.vue";
import MetadataCreditsTable from "@/components/metadata/credits-table.vue";
import MetadataTags from "@/components/metadata/metadata-tags.vue";
import MetadataText from "@/components/metadata/metadata-text.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { getDateTime } from "@/datetime";
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
const FILE_FORMATS = {
  comic: "Comic Archive",
  pdf: "PDF",
};

export default {
  name: "MetadataButton",
  components: {
    BookCover,
    CloseButton,
    MetadataCreditsTable,
    MetadataTags,
    MetadataText,
    PlaceholderLoading,
  },
  props: {
    group: {
      type: String,
      required: true,
    },
    pk: {
      type: Number,
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
    }),
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
      downloadFileName: (state) => {
        const md = state.md;
        return state.md.path
          ? md.path.split("/").at(-1)
          : getFullComicName({
              seriesName: md.series.name,
              volumeName: md.volume.name,
              issue: md.issue,
              issueSuffix: md.issueSuffix,
            }) + ".cbz";
      },
    }),
    ...mapState(useBrowserStore, {
      q: (state) => state.settings.q,
    }),
    downloadURL: function () {
      return getDownloadURL(this.pk);
    },
    isReadButtonShown: function () {
      return this.group === "c" && this.$route.name != "reader";
    },
    isReadButtonEnabled: function () {
      return this.$route.name === "browser" && Boolean(this.readerRoute);
    },
    readButtonIcon: function () {
      return this.isReadButtonEnabled ? mdiEye : mdiEyeOff;
    },
    readerRoute: function () {
      return getReaderRoute(this.md);
    },
    formattedIssue: function () {
      if (
        (this.md.issue === null || this.md.issue === undefined) &&
        !this.md.issueSuffix
      ) {
        // comic-name.formattedIssue() shows 0 for null issue.
        return;
      }
      return formattedIssue({
        issue: this.md.issue,
        issueSuffix: this.md.issueSuffix,
      });
    },
    ltrText: function () {
      return this.md.readLtr ? "Left to Right" : "Right to Left";
    },
    pages: function () {
      let pages = "";
      if (this.md.page) {
        const humanBookmark = humanize.numberFormat(this.md.page, 0);
        pages += `Read ${humanBookmark} of `;
      }
      const humanPages = humanize.numberFormat(this.md.pageCount, 0);
      pages += `${humanPages} pages`;
      if (this.md.progress > 0) {
        pages += ` (${Math.round(this.md.progress)}%)`;
      }
      return pages;
    },
    size: function () {
      return humanize.filesize(this.md.size);
    },
    fileFormat: function () {
      return FILE_FORMATS[this.md.fileFormat] || this.md.fileFormat;
    },
  },
  watch: {
    dialog: function (to) {
      if (to) {
        this.dialogOpened();
      } else {
        this.clearMetadata();
      }
    },
  },
  mounted() {
    window.addEventListener("keyup", this._keyListener);
  },
  unmounted() {
    window.removeEventListener("keyup", this._keyListener);
  },
  methods: {
    ...mapActions(useMetadataStore, ["clearMetadata", "loadMetadata"]),
    ...mapActions(useCommonStore, ["downloadIOSPWAFix"]),
    dialogOpened: function () {
      this.loadMetadata({
        group: this.group,
        pk: this.pk,
      });
      this.startProgress();
    },
    startProgress: function () {
      this.startTime = Date.now();
      this.estimatedMS =
        Math.max(MIN_SECS, this.children / CHILDREN_PER_SECOND) * 1000;
      this.updateProgress();
    },
    updateProgress: function () {
      const elapsed = Date.now() - this.startTime;
      this.progress = (elapsed / this.estimatedMS) * 100;
      if (this.progress >= 100 || this.md) {
        return;
      }
      setTimeout(() => {
        this.updateProgress();
      }, UPDATE_INTERVAL);
    },
    formatDateTime: function (ds) {
      return getDateTime(ds, this.twentyFourHourTime);
    },
    download() {
      this.downloadIOSPWAFix(this.downloadURL, this.downloadFileName);
    },
    _keyListener(event) {
      event.stopImmediatePropagation();
      if (event.key === "Escape") {
        this.dialog = false;
      }
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
#metadataBody {
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
.inlineRow > * {
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
.headerHalfRow > * {
  width: calc((100vw - 175px) / 2);
  display: inline-flex;
}
.headerQuarterRow > * {
  width: calc((100vw - 175px) / 4);
  display: inline-flex;
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
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #metadataContainer {
    font-size: 12px;
  }
}
</style>
