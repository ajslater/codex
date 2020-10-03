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
            :cover-path="md.container.x_cover_path"
            :group="group"
            :child-count="md.pks.length"
            :finished="md.container.finished"
          />
          <v-progress-linear
            class="bookCoverProgress"
            :value="md.container.progress"
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
          :value="md.comic.publisher"
          label="Publisher"
          :show="editMode"
        />
        <MetadataCombobox
          class="imprint"
          :value="md.comic.imprint"
          label="Imprint"
          :show="editMode"
        />
        <MetadataCombobox
          :value="md.comic.series"
          label="Series"
          :show="editMode"
        />
        <div class="publishRow">
          <MetadataCombobox
            id="volume"
            class="halfWidth"
            :value="md.comic.volume"
            label="Volume"
            :show="editMode"
          />
          <MetadataCombobox
            class="halfWidth"
            :value="md.comic.volume_count"
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
            :value="md.comic.issue_count"
            label="Issue Count"
            :show="editMode"
          />
        </div>
        <MetadataCombobox
          :value="md.comic.title"
          label="Title"
          :show="editMode"
        />
      </header>

      <div id="metadataTable">
        <span
          v-if="editMode || md.comic.year || md.comic.month || md.comic.day"
          id="dateRow"
        >
          <MetadataAutocomplete
            :show="editMode"
            :value="md.comic.year"
            label="Year"
            class="datePicker"
            type="number"
          />
          <MetadataAutocomplete
            :show="editMode"
            :value="md.comic.month"
            label="Month"
            class="datePicker"
          />
          <MetadataAutocomplete
            :show="editMode"
            :value="md.comic.day"
            label="Day"
            class="datePicker"
          />
        </span>
        <span id="uneditableMetadata">
          <span>
            <span v-if="md.container.bookmark"
              >Read {{ md.container.bookmark }} of </span
            >{{ md.container.x_page_count }} Pages
            <span v-if="md.comic.finished">, Finished</span>
          </span>
          <span id="size">
            {{ md.container.size | bytes }}
          </span>
        </span>

        <MetadataCombobox
          :show="editMode"
          :value="md.comic.format"
          label="Format"
        />
        <MetadataCombobox
          :show="editMode"
          :value="md.comic.country"
          label="Country"
        />
        <MetadataCombobox
          :show="editMode"
          :value="md.comic.language"
          label="Language"
        />
        <a
          v-if="md.comic.web && !editMode"
          id="webLink"
          :href="md.comic.web"
          target="_blank"
        >
          <MetadataCombobox
            :show="editMode"
            :value="md.comic.web"
            label="Web Link"
          />
        </a>
        <MetadataCombobox
          v-else-if="editMode"
          :show="editMode"
          :value="md.comic.web"
          label="Web Link"
        />
        <MetadataAutocomplete
          :show="editMode"
          :value="md.comic.user_rating"
          label="User Rating"
        />
        <MetadataAutocomplete
          :show="editMode"
          :value="md.comic.critical_rating"
          label="Critical Rating"
        />
        <MetadataAutocomplete
          :show="editMode"
          :value="md.comic.maturity_rating"
          label="Maturity Rating"
        />
        <MetadataTags
          :show="editMode"
          :values="md.comic.genres"
          label="Genres"
        />
        <MetadataTags :show="editMode" :values="md.comic.tags" label="Tags" />
        <MetadataTags :show="editMode" :values="md.comic.teams" label="Teams" />
        <MetadataTags
          :show="editMode"
          :values="md.comic.characters"
          label="Characters"
        />
        <MetadataTags
          :show="editMode"
          :values="md.comic.locations"
          label="Locations"
        />
        <MetadataTags
          :show="editMode"
          :values="md.comic.story_arcs"
          label="Story Arcs"
        />
        <MetadataTags
          :show="editMode"
          :values="md.comic.series_groups"
          label="Series Groups"
        />
        <MetadataCombobox
          :show="editMode"
          :value="md.comic.scan_info"
          label="Scan"
        />
        <MetadataTextArea
          :show="editMode"
          :value="md.comic.summary"
          label="Summary"
        />
        <MetadataTextArea
          :show="editMode"
          :value="md.comic.description"
          label="Description"
        />
        <MetadataTextArea
          :show="editMode"
          :value="md.comic.notes"
          label="Notes"
        />
        <table
          v-if="md.comic.credits && md.comic.credits.length > 0"
          id="creditsTable"
        >
          <thead>
            <tr>
              <th id="creditsTitle" colspan="2">
                <h2>Credits</h2>
              </th>
            </tr>
            <tr>
              <th>Role</th>
              <th>Person</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="credit in md.comic.credits" :key="credit.pk">
              <td>
                <MetadataAutocomplete :value="credit.role" />
              </td>
              <td>
                <MetadataCombobox :value="credit.person" />
              </td>
            </tr>
          </tbody>
        </table>
        <div>
          <MetadataCheckbox
            :show="editMode"
            class="ltrCheckbox"
            :value="md.comic.read_ltr"
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
      <!-- TODO remove if fast metadata tests fast -->
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

import { getDownloadURL } from "@/api/v1/metadata";
import BookCover from "@/components/book-cover";
import MetadataAutocomplete from "@/components/metadata-autocomplete";
import MetadataCheckbox from "@/components/metadata-checkbox";
import MetadataCombobox from "@/components/metadata-combobox";
import MetadataSwitch from "@/components/metadata-switch";
import MetadataTags from "@/components/metadata-tags";
import MetadataTextArea from "@/components/metadata-textarea";
import { getReaderRoute } from "@/router/route";

// TODO remove if fast metadata tests fast
const CHILDREN_PER_SECOND = 9; // ~10 on my machine
const UPDATE_INTERVAL = 250;

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
      progress: 0, // TODO remove if placeholder goes away
      estimatedTime: 0,
      startTime: 0,
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
      const decimalIssue = this.md.comic.issue;
      if (decimalIssue == null) {
        return;
      }
      let issueStr = Math.floor(decimalIssue).toString();
      if (decimalIssue % 1 != 0) {
        // XXX Janky only handles half issues.
        issueStr += "½";
      }
      return issueStr;
    },
    singleComicPK: function () {
      return this.md.pks[0];
    },
    downloadURL: function () {
      return getDownloadURL(this.singleComicPK);
    },
    readerRoute: function () {
      const pk = this.singleComicPK;
      const bookmark = this.md.container.bookmark;
      const readLTR = this.md.comic.read_ltr;
      const pageCount = this.md.container.x_page_count;
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
  /*
  // TODO ask large library person to time metadata and see if this is
  //  useful
  watch: {
    md: function (newMD) {
      if (newMD == null) {
        this.startTime = new Date().getTime();
        return;
      }
      const endTime = new Date().getTime();
      const elapsed = (endTime - this.startTime) / 1000;
      const numChildren = newMD.pks.length;
      const cps = numChildren / elapsed;
      console.debug(`${numChildren} / ${elapsed} secs = ${cps} CPS`);
    },
  },
  */
  methods: {
    dialogOpened: function () {
      this.$store.dispatch("metadata/metadataOpened", {
        group: this.group,
        pk: this.pk,
      });
      this.startTime = Date.now();
      this.estimatedTime = (this.children / CHILDREN_PER_SECOND) * 1000;
      this.updateProgress();
    },
    dialogClosed: function () {
      this.dialog = false;
      this.$store.dispatch("metadata/metadataClosed");
    },
    updateProgress: function () {
      // TODO remove if fast metadata tests fast
      const elapsed = Date.now() - this.startTime;
      this.progress = (elapsed / this.estimatedTime) * 100;
      if (this.progress >= 100 || this.md) {
        return;
      }
      const that = this;
      setTimeout(function () {
        that.updateProgress();
      }, UPDATE_INTERVAL);
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
#size {
  padding-left: 1em;
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
</style>

<!-- eslint-disable vue-scoped-css/require-scoped -->
<style lang="scss">
.v-dialog--fullscreen {
  width: 100% !important;
  opacity: 0.99;
}
</style>
<!-- eslint-enable vue-scoped-css/require-scoped -->
