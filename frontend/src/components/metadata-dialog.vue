<template>
  <v-dialog
    v-model="dialog"
    fullscreen
    transition="dialog-bottom-transition"
    class="metadataDialog"
  >
    <template #activator="{ on }">
      <v-icon class="metadataButton" v-on="on">
        {{ mdiTagOutline }}
      </v-icon>
    </template>
    <div v-if="md" id="metadataContainer">
      <header id="metadataHeader">
        <div id="metadataBookCoverWrapper">
          <BookCover
            id="bookCover"
            :cover-path="md.cover_path"
            :group="group"
            :child-count="md.child_count"
            :finished="md.finished"
          />
          <v-progress-linear
            class="bookCoverProgress"
            :value="md.progress"
            rounded
            background-color="inherit"
            height="2"
          />
        </div>
        <v-btn
          id="topCloseButton"
          title="Close Metadata (esc)"
          ripple
          @click="dialog = false"
          >x</v-btn
        >
        <MetadataText id="publisher" :value="md.publisher" label="Publisher" />
        <MetadataText id="imprint" :value="md.imprint" label="Imprint" />
        <MetadataText id="series" :value="md.series" label="Series" />
        <div class="inlineRow">
          <MetadataText
            id="volume"
            class="halfWidth"
            :value="md.volume"
            label="Volume"
          />
          <MetadataText
            class="halfWidth"
            :value="md.volume_count"
            label="Volume Count"
          />
        </div>
        <div class="inlineRow">
          <MetadataText
            id="issue"
            class="halfWidth"
            :value="formattedIssue"
            label="Issue"
          />
          <MetadataText
            class="halfWidth"
            :value="md.issue_count"
            label="Issue Count"
          />
        </div>
        <MetadataText :value="md.name" label="Title" />
        <span v-if="md.year || md.month || md.day" class="inlineRow">
          <MetadataText
            :value="md.year"
            label="Year"
            class="datePicker"
            type="number"
          />
          <MetadataText :value="md.month" label="Month" class="datePicker" />
          <MetadataText :value="md.day" label="Day" class="datePicker" />
        </span>
        <MetadataText :value="md.format" label="Format" />
      </header>
      <div id="metadataBody">
        <section class="mdSection">
          <div class="inlineRow">
            <MetadataText id="pages" :value="pages" label="Pages" />
            <MetadataCheckbox
              id="finished"
              :value="md.finished"
              label="Finished"
            />
            <MetadataText :value="ltrText" label="Reading Direction" />
          </div>
        </section>
        <section class="mdSection">
          <div class="inlineRow">
            <MetadataText
              :value="formatDateTime(md.created_at)"
              label="Created at"
              class="mtime"
            />
            <MetadataText
              :value="formatDateTime(md.updated_at)"
              label="Updated at"
              class="mtime"
            />
          </div>
          <MetadataText :value="md.path" label="Path" />
          <MetadataText :value="md.size | bytes" label="Size" />
        </section>
        <section class="inlineRow section">
          <MetadataText :value="md.country" label="Country" />
          <MetadataText :value="md.language" label="Language" />
        </section>
        <section class="mdSection">
          <MetadataText :value="md.user_rating" label="User Rating" />
          <MetadataText :value="md.critical_rating" label="Critical Rating" />
          <MetadataText :value="md.maturity_rating" label="Maturity Rating" />
        </section>
        <section class="mdSection">
          <MetadataTags :values="md.genres" label="Genres" />
          <MetadataTags :values="md.tags" label="Tags" />
          <MetadataTags :values="md.teams" label="Teams" />
          <MetadataTags :values="md.characters" label="Characters" />
          <MetadataTags :values="md.locations" label="Locations" />
          <MetadataTags :values="md.story_arcs" label="Story Arcs" />
          <MetadataTags :values="md.series_groups" label="Series Groups" />
        </section>
        <section class="mdSection">
          <MetadataText :value="md.web" label="Web Link" :link="true" />
          <MetadataText :value="md.summary" label="Summary" />
          <MetadataText :value="md.description" label="Description" />
          <MetadataText :value="md.notes" label="Notes" />
          <MetadataText :value="md.scan_info" label="Scan" />
        </section>
        <section class="mdSection">
          <v-simple-table v-if="md.credits && md.credits.length > 0">
            <template #default>
              <h2>Creators</h2>
              <table id="creditsTable">
                <thead>
                  <tr>
                    <th class="text-left">Role</th>
                    <th class="text-left">Creator</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="credit in md.credits" :key="credit.pk">
                    <td>
                      {{ credit.role.name }}
                    </td>
                    <td>
                      {{ credit.person.name }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </template>
          </v-simple-table>
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
          v-if="isBrowser && group === 'c'"
          :to="readerRoute"
          title="Read Comic"
        >
          <v-icon>{{ mdiEye }}</v-icon>
        </v-btn>

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
      />
    </div>
  </v-dialog>
</template>
<script>
import { mdiDownload, mdiEye, mdiTagOutline } from "@mdi/js";
import { mapGetters, mapState } from "vuex";

import { getDownloadURL } from "@/api/v2/comic";
import BookCover from "@/components/book-cover";
import { formattedIssue } from "@/components/comic-name";
import MetadataCheckbox from "@/components/metadata-checkbox";
import MetadataTags from "@/components/metadata-tags";
import MetadataText from "@/components/metadata-text";
import { getReaderRoute } from "@/router/route";

// Progress circle
// Can take 19 seconds for 22k children on huge collections
const CHILDREN_PER_SECOND = 1160;
const MIN_SECS = 0.05;
const UPDATE_INTERVAL = 250;

const DATE_OPTIONS = {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
};

export default {
  name: "MetadataButton",
  components: {
    BookCover,
    MetadataCheckbox,
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
      mdiTagOutline,
      dialog: false,
      progress: 0,
    };
  },
  computed: {
    ...mapState("metadata", {
      md: (state) => state.md,
    }),
    ...mapGetters("auth", ["isAdmin"]),
    isBrowser: function () {
      return this.$route.name === "browser";
    },
    formattedIssue: function () {
      return formattedIssue(this.md.issue);
    },
    downloadURL: function () {
      return getDownloadURL(this.md.id);
    },
    readerRoute: function () {
      const pk = this.md.id;
      const bookmark = this.md.bookmark;
      const readLTR = this.md.read_ltr;
      const pageCount = this.md.page_count;
      return getReaderRoute(pk, bookmark, readLTR, pageCount);
    },
    ltrText: function () {
      return this.md.read_ltr ? "Left to Right" : "Right to Left";
    },
    pages: function () {
      let pages = "";
      if (this.md.bookmark) {
        pages += `Read ${this.md.bookmark} of `;
      }
      pages += `${this.md.page_count} pages`;
      if (this.md.progress > 0) {
        pages += ` (${Math.round(this.md.progress)}%)`;
      }
      return pages;
    },
  },
  watch: {
    dialog: function (to) {
      if (to) {
        this.dialogOpened();
      } else {
        this.dialogClosed();
      }
    },
  },
  methods: {
    dialogOpened: function () {
      this.$store.dispatch("metadata/metadataOpened", {
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
    dialogClosed: function () {
      this.$store.dispatch("metadata/metadataClosed");
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
      return new Intl.DateTimeFormat("en-US", DATE_OPTIONS).format(dt);
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
#bookCover,
#publisher,
#imprint {
  padding-top: 0px !important;
}
.inlineRow > * {
  display: inline-flex;
}
#publisher,
#imprint {
  width: 35%;
}
.mdSection {
  margin-top: 25px;
}
#pages {
  width: 225px;
}
#finished {
  margin-left: 10px;
  margin-right: 10px;
}
.datePicker {
  width: 90px;
  display: inline-block;
}
#creditsTable th,
#creditsTable td {
  padding: 10px;
}
#creditsTable tr:nth-child(even) {
  background-color: #282828;
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
.halfWidth {
  display: inline-block;
}
.mtime {
  width: 210px;
}
.placeholder {
  margin-top: 48px;
}
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #metadataContainer {
    font-size: 12px;
  }
  #publisher,
  #imprint,
  #series {
    padding-top: 15px !important;
    width: 100%;
  }
  .halfWidth {
    width: 50%;
  }
  .datePicker {
    min-width: 65px;
    width: 33%;
  }
}
/* eslint-disable-next-line vue-scoped-css/no-unused-selector */
.v-dialog--fullscreen {
  width: 100% !important;
  opacity: 0.99;
}
#metadataContainer,
#placeholderContainer {
  padding: 20px;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
.v-dialog {
  /* Seems like I'm fixing a bug here */
  background-color: #121212;
}
</style>
