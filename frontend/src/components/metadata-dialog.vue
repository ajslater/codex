<template>
  <v-dialog
    v-model="dialog"
    fullscreen
    transition="dialog-bottom-transition"
    class="metadataDialog"
  >
    <template #activator="{ on }">
      <v-icon class="metadataButton" v-on="on" @click="metadataOpened()">
        {{ mdiTagOutline }}
      </v-icon>
    </template>
    <div v-if="comic" id="metadataContainer">
      <header id="metadataHeader">
        <div id="metadataBookCoverWrapper">
          <BookCover
            id="bookCover"
            :cover-path="comic.coverPath"
            :group="group"
            :child-count="comic.pks.length"
            :finished="comic.finished"
          />
          <v-progress-linear
            class="bookCoverProgress"
            :value="comic.progress"
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
        <MetadataCombobox
          class="publisher"
          :items="comic.publisherChoices"
          label="Publisher"
          :show="editMode"
        />
        <MetadataCombobox
          class="imprint"
          :items="comic.imprintChoices"
          label="Imprint"
          :show="editMode"
        />
        <MetadataCombobox
          :items="comic.seriesChoices"
          label="Series"
          :show="editMode"
        />
        <div class="publishRow">
          <MetadataCombobox
            id="volume"
            class="halfWidth"
            :items="comic.volumeChoices"
            label="Volume"
            :show="editMode"
          />
          <MetadataCombobox
            class="halfWidth"
            :items="comic.volumeCountChoices"
            label="Volume Count"
            :show="editMode"
          />
        </div>
        <div id="issueRow" class="publishRow">
          <MetadataCombobox
            id="issue"
            class="halfWidth"
            :values="formattedIssueChoices"
            label="Issue"
            :show="editMode"
          />
          <MetadataCombobox
            class="halfWidth"
            :values="comic.issueCountChoices"
            label="Issue Count"
            :show="editMode"
          />
        </div>
        <MetadataCombobox
          :values="comic.titleChoices"
          label="Title"
          :show="editMode"
        />
      </header>

      <div id="metadataTable">
        <span
          v-if="
            editMode ||
            comic.yearChoices ||
            comic.monthChoices ||
            comic.dayChoices
          "
          id="dateRow"
        >
          <MetadataAutocomplete
            :show="editMode"
            :values="comic.yearChoices"
            label="Year"
            class="datePicker"
            type="number"
          />
          <MetadataAutocomplete
            :show="editMode"
            :values="comic.monthChoices"
            label="Month"
            class="datePicker"
          />
          <MetadataAutocomplete
            :show="editMode"
            :values="comic.dayChoices"
            label="Day"
            class="datePicker"
          />
        </span>
        <span id="uneditableMetadata">
          <span>
            <span v-if="comic.bookmark">Read {{ comic.bookmark }} of </span
            >{{ comic.pageCount }} Pages
            <span v-if="comic.finished">, Finished</span>
          </span>
          <span id="size">
            {{ comic.size | bytes }}
          </span>
        </span>

        <MetadataCombobox
          :show="editMode"
          :values="comic.formatChoices"
          label="Format"
        />
        <MetadataCombobox
          :show="editMode"
          :items="comic.countryChoices"
          label="Country"
        />
        <MetadataCombobox
          :show="editMode"
          :items="comic.languageChoices"
          label="Language"
        />
        <a
          v-if="comic.webChoices && comic.webChoices.length === 1 && !editMode"
          id="webLink"
          :href="comic.webChoices[0]"
          target="_blank"
        >
          <MetadataCombobox
            :show="editMode"
            :values="comic.webChoices"
            label="Web Link"
          />
        </a>
        <MetadataCombobox
          v-else-if="editMode"
          :show="editMode"
          :items="comic.webChoices"
          label="Web Link"
        />
        <MetadataAutocomplete
          :show="editMode"
          :items="comic.userRatingChoices"
          label="User Rating"
        />
        <MetadataAutocomplete
          :show="editMode"
          :items="comic.criticalRatingChoices"
          label="Critical Rating"
        />
        <MetadataAutocomplete
          :show="editMode"
          :items="comic.maturityRatingChoices"
          label="Maturity Rating"
        />
        <MetadataTags
          :show="editMode"
          :items="comic.genresChoices"
          label="Genres"
        />
        <MetadataTags
          :show="editMode"
          :items="comic.tagsChoices"
          label="Tags"
        />
        <MetadataTags
          :show="editMode"
          :items="comic.teamsChoices"
          label="Teams"
        />
        <MetadataTags
          :show="editMode"
          :items="comic.charactersChoices"
          label="Characters"
        />
        <MetadataTags
          :show="editMode"
          :items="comic.locationsChoices"
          label="Locations"
        />
        <MetadataTags
          :show="editMode"
          :items="comic.storyArcsChoices"
          label="Story Arcs"
        />
        <MetadataTags
          :show="editMode"
          :items="comic.seriesGroupsChoices"
          label="Series Groups"
        />
        <MetadataCombobox
          :show="editMode"
          :items="comic.scanInfoChoices"
          label="Scan"
        />
        <MetadataTextArea
          :show="editMode"
          :value="comic.summary"
          label="Summary"
        />
        <MetadataTextArea
          :show="editMode"
          :value="comic.description"
          label="Description"
        />
        <MetadataTextArea :show="editMode" :value="comic.notes" label="Notes" />
        <table
          v-if="comic.creditsChoices && comic.creditsChoices.length > 0"
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
            <tr v-for="credit in comic.creditsChoices" :key="credit.pk">
              <td>
                <MetadataAutocomplete :items="[credit.role]" />
              </td>
              <td>
                <MetadataCombobox :items="[credit.person]" />
              </td>
            </tr>
          </tbody>
        </table>
        <div>
          <MetadataCheckbox
            :show="editMode"
            class="ltrCheckbox"
            :values="comic.readLTRChoices"
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

import { getDownloadURL } from "@/api/v1/metadata";
import BookCover from "@/components/book-cover";
import MetadataAutocomplete from "@/components/metadata-autocomplete";
import MetadataCheckbox from "@/components/metadata-checkbox";
import MetadataCombobox from "@/components/metadata-combobox";
import MetadataSwitch from "@/components/metadata-switch";
import MetadataTags from "@/components/metadata-tags";
//import MetadataTextField from "@/components/metadata-text-field";
import MetadataTextArea from "@/components/metadata-textarea";
//import PlaceholderLoading from "@/components/placeholder-loading";
import { getReaderRoute } from "@/router/route";

const CHILDREN_PER_SECOND = 8;
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
    // PlaceholderLoading,
    // MetadataTextField,
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
      estimatedTime: 0,
      startTime: 0,
    };
  },
  computed: {
    ...mapState("metadata", {
      comic: (state) => state.comic,
    }),
    ...mapGetters("auth", ["isAdmin"]),
    isBrowser: function () {
      return this.$route.name === "browser";
    },
    formattedIssueChoices: function () {
      const result = [];
      if (!this.comic.issueChoices) {
        return null;
      }
      this.comic.issueChoices.forEach(function (issue) {
        let issueStr = Math.floor(issue).toString();
        if (issue % 1 != 0) {
          // XXX Janky only handles half issues.
          issueStr += "½";
        }
        result.push(issueStr);
      });
      return result;
    },
    downloadURL: function () {
      return getDownloadURL(this.comic.pk);
    },
    readerRoute: function () {
      const pk = this.comic.pks[0];
      const bookmark = this.comic.bookmark;
      const readLTR = this.comic.readLTRChoices[0];
      const pageCount = this.comic.pageCount;
      return getReaderRoute(pk, bookmark, readLTR, pageCount);
    },
    saveButtonLabel: function () {
      let label = "Save ";
      if (this.group === "c" && this.comic.pks.length === 1) {
        label += "Comic";
      } else {
        const length = this.comic.pks.length;
        label += `${length} Comic`;
        if (length > 1) {
          label += "s";
        }
      }
      return label;
    },
  },
  methods: {
    metadataOpened: function () {
      this.$store.dispatch("metadata/comicMetadataOpened", {
        group: this.group,
        pk: this.pk,
      });
      this.startTime = Date.now();
      this.estimatedTime = (this.children / CHILDREN_PER_SECOND) * 1000;
      this.updateProgress();
    },
    updateProgress: function () {
      const elapsed = Date.now() - this.startTime;
      this.progress = (elapsed / this.estimatedTime) * 100;
      if (this.progress >= 100 || this.comic) {
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
