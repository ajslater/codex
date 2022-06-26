<template>
  <v-dialog
    v-model="dialog"
    fullscreen
    transition="dialog-bottom-transition"
    content-class="metadataDialog"
  >
    <template #activator="{ on }">
      <v-icon class="metadataButton" aria-label="tags" v-on="on">
        {{ mdiTagOutline }}
      </v-icon>
    </template>
    <div v-if="md" id="metadataContainer">
      <header id="metadataHeader">
        <v-btn
          id="topCloseButton"
          title="Close Metadata (esc)"
          ripple
          @click="dialog = false"
          >x</v-btn
        >
        <MetadataText
          v-if="autoquery"
          id="search"
          :value="autoquery"
          label="Search Query"
          :highlight="true"
        />
        <div id="metadataBookCoverWrapper">
          <BookCover
            id="bookCover"
            :cover-path="md.coverPath"
            :group="group"
            :child-count="md.childCount"
            :finished="md.finished"
          />
          <v-progress-linear
            class="bookCoverProgress"
            :value="md.progress"
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
          :href="downloadURL"
          download
          title="Download Comic Archive"
          ><v-icon v-if="group === 'c'">{{ mdiDownload }}</v-icon></v-btn
        >
        <v-btn
          v-if="isBrowser && group === 'c' && readerRoute"
          :to="readerRoute"
          title="Read Comic"
        >
          <v-icon>{{ mdiEye }}</v-icon>
        </v-btn>
        <v-icon v-else-if="group === 'c' && !readerRoute">{{
          mdiEyeOff
        }}</v-icon>

        <span id="bottomRightButtons">
          <v-btn
            id="bottomCloseButton"
            ripple
            title="Close Metadata (esc)"
            @click="dialog = false"
            >x</v-btn
          >
        </span>
      </footer>
    </div>
    <div v-else id="placeholderContainer">
      <v-btn
        id="topCloseButton"
        title="Close Metadata (esc)"
        ripple
        @click="dialog = false"
        >x</v-btn
      >
      <div id="placeholderTitle">Tags Loading</div>
      <v-progress-circular
        :value="progress"
        :indeterminate="progress >= 100"
        size="256"
        color="#cc7b19"
        class="placeholder"
        aria-label="tags loading"
      />
    </div>
  </v-dialog>
</template>
<script>
import { mdiDownload, mdiEye, mdiEyeOff, mdiTagOutline } from "@mdi/js";
import humanize from "humanize";
import { mapActions, mapGetters, mapState } from "vuex";

import { getDownloadURL } from "@/api/v2/comic";
import BookCover from "@/components/book-cover";
import { formattedIssue } from "@/components/comic-name.js";
import { DATETIME_FORMAT } from "@/components/datetime";
import MetadataCreditsTable from "@/components/metadata-credits-table";
import MetadataTags from "@/components/metadata-tags";
import MetadataText from "@/components/metadata-text";
import { getReaderRoute } from "@/router/route";

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
    MetadataCreditsTable,
    MetadataTags,
    MetadataText,
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
      mdiEye,
      mdiEyeOff,
      mdiTagOutline,
      dialog: false,
      progress: 0,
    };
  },
  computed: {
    ...mapState("metadata", {
      md: (state) => state.md,
      downloadURL: function (state) {
        return getDownloadURL(this.md.pk, state.timestamp);
      },
    }),
    ...mapState("browser", {
      autoquery: (state) => state.settings.autoquery,
    }),
    ...mapGetters("auth", ["isAdmin"]),
    isBrowser: function () {
      return this.$route.name === "browser";
    },
    formattedIssue: function () {
      if (
        (this.issue === null || this.issue === undefined) &&
        !this.issueSuffix
      ) {
        // comic-name.formattedIssue() shows 0 for null issue.
        return;
      }
      return formattedIssue({
        issue: this.md.issue,
        issueSuffix: this.md.issueSuffix,
      });
    },
    readerRoute: function () {
      return getReaderRoute(this.md);
    },
    ltrText: function () {
      return this.md.readLtr ? "Left to Right" : "Right to Left";
    },
    pages: function () {
      let pages = "";
      if (this.md.bookmark) {
        const humanBookmark = humanize.numberFormat(this.md.bookmark, 0);
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
        this.metadataClosed();
      }
    },
  },
  methods: {
    ...mapActions("metadata", ["metadataClosed", "metadataOpened"]),
    dialogOpened: function () {
      this.metadataOpened({
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
      const dt = new Date(ds);
      return DATETIME_FORMAT.format(dt);
    },
  },
};
</script>

<style scoped lang="scss">
@import "~vuetify/src/styles/styles.sass";
#metadataContainer {
  display: flex;
  flex-direction: column;
  max-width: 100vw;
  background-color: #121212;
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
  color: gray;
}
#topCloseButton {
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
#topCloseButton,
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
.placeholder {
  margin-top: 48px;
}
#metadataContainer,
#placeholderContainer {
  padding: 20px;
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

@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #metadataContainer {
    font-size: 12px;
  }
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
.v-dialog {
  /* Seems like I'm fixing a bug here */
  background-color: #121212;
}
</style>
