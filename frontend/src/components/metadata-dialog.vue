<template>
  <v-dialog
    v-model="dialog"
    fullscreen
    transition="dialog-bottom-transition"
    class="metadataDialog"
  >
    <template #activator="{ on }">
      <v-icon class="metadataButton" v-on="on" @click="dialogOpened()">
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
          @click="dialogClosed()"
          >x</v-btn
        >
        <MetadataCombobox
          class="publisher"
          :value="md.publisher"
          label="Publisher"
          :show="editMode"
        />
        <MetadataCombobox
          class="imprint"
          :value="md.imprint"
          label="Imprint"
          :show="editMode"
        />
        <MetadataCombobox :value="md.series" label="Series" :show="editMode" />
        <div class="publishRow">
          <MetadataCombobox
            id="volume"
            class="halfWidth"
            :value="md.volume"
            label="Volume"
            :show="editMode"
          />
          <MetadataCombobox
            class="halfWidth"
            :value="md.volume_count"
            label="Volume Count"
            :show="editMode"
          />
        </div>
        <div id="issueRow" class="publishRow">
          <MetadataCombobox
            id="issue"
            class="halfWidth"
            :value="formattedIssue"
            label="Issue"
            :show="editMode"
          />
          <MetadataCombobox
            class="halfWidth"
            :value="md.issue_count"
            label="Issue Count"
            :show="editMode"
          />
        </div>
        <MetadataCombobox :value="md.name" label="Title" :show="editMode" />
      </header>

      <div id="metadataTable">
        <span v-if="editMode || md.year || md.month || md.day" id="dateRow">
          <MetadataAutocomplete
            :show="editMode"
            :value="md.year"
            label="Year"
            class="datePicker"
            type="number"
          />
          <MetadataAutocomplete
            :show="editMode"
            :value="md.month"
            label="Month"
            class="datePicker"
          />
          <MetadataAutocomplete
            :show="editMode"
            :value="md.day"
            label="Day"
            class="datePicker"
          />
        </span>
        <span id="uneditableMetadata">
          <div>
            <span>
              <span v-if="md.bookmark">Read {{ md.bookmark }} of </span
              >{{ md.page_count }} Pages
              <span v-if="md.finished">, Finished</span>
            </span>
            <span id="size">
              {{ md.size | bytes }}
            </span>
          </div>
          <table id="mtime">
            <tr v-if="md.created_at" id="created_at">
              <td>Created at</td>
              <td>{{ formatDatetime(md.created_at) }}</td>
            </tr>
            <tr v-if="md.updated_at" id="updated_at">
              <td>Updated at</td>
              <td>{{ formatDatetime(md.updated_at) }}</td>
            </tr>
          </table>
          <span v-if="md.path"> Path: {{ md.path }} </span>
        </span>

        <MetadataCombobox :show="editMode" :value="md.format" label="Format" />
        <MetadataCombobox
          :show="editMode"
          :value="md.country"
          label="Country"
        />
        <MetadataCombobox
          :show="editMode"
          :value="md.language"
          label="Language"
        />
        <a
          v-if="md.web && !editMode"
          id="webLink"
          :href="md.web"
          target="_blank"
        >
          <MetadataCombobox :show="editMode" :value="md.web" label="Web Link" />
        </a>
        <MetadataCombobox
          v-else-if="editMode"
          :show="editMode"
          :value="md.web"
          label="Web Link"
        />
        <MetadataAutocomplete
          :show="editMode"
          :value="md.user_rating"
          label="User Rating"
        />
        <MetadataAutocomplete
          :show="editMode"
          :value="md.critical_rating"
          label="Critical Rating"
        />
        <MetadataAutocomplete
          :show="editMode"
          :value="md.maturity_rating"
          label="Maturity Rating"
        />
        <MetadataTags :show="editMode" :values="md.genres" label="Genres" />
        <MetadataTags :show="editMode" :values="md.tags" label="Tags" />
        <MetadataTags :show="editMode" :values="md.teams" label="Teams" />
        <MetadataTags
          :show="editMode"
          :values="md.characters"
          label="Characters"
        />
        <MetadataTags
          :show="editMode"
          :values="md.locations"
          label="Locations"
        />
        <MetadataTags
          :show="editMode"
          :values="md.story_arcs"
          label="Story Arcs"
        />
        <MetadataTags
          :show="editMode"
          :values="md.series_groups"
          label="Series Groups"
        />
        <MetadataCombobox :show="editMode" :value="md.scan_info" label="Scan" />
        <MetadataTextArea
          :show="editMode"
          :value="md.summary"
          label="Summary"
        />
        <MetadataTextArea
          :show="editMode"
          :value="md.description"
          label="Description"
        />
        <MetadataTextArea :show="editMode" :value="md.notes" label="Notes" />
        <table v-if="md.credits && md.credits.length > 0" id="creditsTable">
          <thead>
            <tr>
              <th id="creditsTitle" colspan="2">
                <h2>Creators</h2>
              </th>
            </tr>
            <tr>
              <th>Role</th>
              <th>Person</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="credit in md.credits" :key="credit.pk">
              <td>
                <MetadataAutocomplete :value="credit.role.name" />
              </td>
              <td>
                <MetadataCombobox :value="credit.person.name" />
              </td>
            </tr>
          </tbody>
        </table>
        <div>
          <MetadataCheckbox
            :show="editMode"
            class="ltrCheckbox"
            :value="md.read_ltr"
            label="Read Left to Right"
            :readonly="true"
          />
          <MetadataSwitch
            v-if="false && isAdmin"
            class="editModeSwitch"
            :value="editMode"
            label="Edit Mode"
            @input="editMode = $event"
          />
        </div>
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
          <v-btn v-if="editMode" id="saveButton" ripple title="Save Metadata">{{
            saveButtonLabel
          }}</v-btn>
          <v-btn
            id="bottomCloseButton"
            ripple
            title="Close Metadata (esc)"
            @click="dialogClosed()"
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
import { formattedIssue } from "@/components/comic-name.js";
import MetadataAutocomplete from "@/components/metadata-autocomplete";
import MetadataCheckbox from "@/components/metadata-checkbox";
import MetadataCombobox from "@/components/metadata-combobox";
import MetadataSwitch from "@/components/metadata-switch";
import MetadataTags from "@/components/metadata-tags";
import MetadataTextArea from "@/components/metadata-textarea";
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
    MetadataAutocomplete,
    MetadataCheckbox,
    MetadataCombobox,
    MetadataSwitch,
    MetadataTags,
    MetadataTextArea,
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
      editMode: false,
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
    singleComicPK: function () {
      return this.md.pks[0];
    },
    downloadURL: function () {
      return getDownloadURL(this.singleComicPK);
    },
    readerRoute: function () {
      const pk = this.singleComicPK;
      const bookmark = this.md.bookmark;
      const readLTR = this.md.read_ltr;
      const pageCount = this.md.page_count;
      return getReaderRoute(pk, bookmark, readLTR, pageCount);
    },
    saveButtonLabel: function () {
      let label = "Save ";
      if (this.group === "c" && this.pks.length === 1) {
        label += "Comic";
      } else {
        const length = this.md.pks.length;
        label += `${length} Comic`;
        if (length > 1) {
          label += "s";
        }
      }
      return label;
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
      this.dialog = false;
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
    formatDatetime: function (ds) {
      const dt = new Date(ds);
      return new Intl.DateTimeFormat("en-US", DATE_OPTIONS).format(dt);
    },
  },
};
</script>

<style scoped lang="scss">
@import "~vuetify/src/styles/styles.sass";
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
.publisher,
.imprint {
  padding-top: 0px !important;
}
.publisher,
.imprint {
  width: 35%;
  display: inline-flex;
}
#issueRow {
  margin-left: 135px;
}
#metadataTable {
  clear: both;
  padding-top: 15px;
}
#metadataHeader > *,
#metadataTable > * {
  padding-top: 15px;
}
#webLink {
  display: block;
}
.ltrCheckbox,
.editModeSwitch {
  display: inline-block !important;
}
.editModeSwitch {
  float: right;
  /*visibility: hidden; */
}
#dateRow {
  margin-right: 1em;
}
.datePicker {
  width: 90px;
  display: inline-block;
}
#creditsTable {
  width: 100%;
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
#saveButton {
  margin-right: 10px;
}
.halfWidth {
  display: inline-block;
}
#mtime {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
  border-collapse: collapse;
}
#mtime td {
  padding-right: 0.25em;
}
.placeholder {
  margin-top: 48px;
}
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  #metadataContainer {
    font-size: 12px;
  }
  .publisher,
  .imprint {
    padding-top: 15px !important;
    width: 100%;
  }
  .halfWidth {
    width: 50%;
  }
  #issueRow {
    margin-left: 0px;
  }
  #dateRow {
    margin-right: 0px;
  }
  .datePicker {
    min-width: 65px;
    width: 33%;
  }
  #metadataTable {
    padding-top: 0px;
  }
  #uneditableMetadata {
    display: block;
    padding-top: 15px;
    padding-left: 0px;
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
