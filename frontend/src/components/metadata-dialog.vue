<template>
  <v-dialog v-model="dialog" fullscreen transition="dialog-bottom-transition">
    <template #activator="{ on }">
      <v-icon v-on="on" @click="metadataOpened(pk)">
        {{ mdiBorderColor }}
      </v-icon>
    </template>
    <div v-if="comic" id="metadataContainer">
      <header id="metadataHeader">
        <BookCover
          id="bookCover"
          :cover-path="comic.cover_path"
          :progress="+comic.progress"
        />
        <v-btn
          id="topCloseButton"
          title="Close Metadata (esc)"
          ripple
          @click="dialog = false"
          >x</v-btn
        >
        <MetadataCombobox
          class="publisher"
          :model="comic.publisher_name"
          label="Publisher"
          :show="true"
        />
        <MetadataCombobox
          class="imprint"
          :model="comic.imprint_name"
          label="Imprint"
          :show="true"
        />
        <MetadataCombobox
          :model="comic.series_name"
          label="Series"
          :show="true"
        />
        <div class="publishRow">
          <MetadataCombobox
            id="volume"
            class="halfWidth"
            :value="comic.volume"
            label="Volume"
            :show="true"
          />
          <MetadataTextField
            class="halfWidth"
            :value="comic.volume_count"
            label="Volume Count"
            :show="editMode"
          />
        </div>
        <div class="publishRow">
          <MetadataTextField
            id="issue"
            class="halfWidth"
            :value="comic.issue"
            label="Issue"
            :show="true"
          />
          <MetadataTextField
            class="halfWidth"
            :value="comic.issue_count"
            label="Issue Count"
            :show="editMode"
          />
        </div>
        <MetadataTextField
          :value="comic.title"
          label="Title"
          :show="editMode"
        />
      </header>

      <div id="metadataTable">
        <span
          v-if="editMode || comic.year || comic.month || comic.day"
          id="dateRow"
        >
          <MetadataTextField
            :show="editMode"
            :value="comic.year ? comic.year.toString() : undefined"
            label="Year"
            class="datePicker"
            type="number"
          />
          <MetadataAutocomplete
            :show="editMode"
            :model="comic.month ? comic.month.toString() : undefined"
            label="Month"
            class="datePicker"
          />
          <MetadataAutocomplete
            :show="editMode"
            :model="comic.day ? comic.day.toString() : undefined"
            label="Day"
            class="datePicker"
          />
        </span>
        <span id="uneditableMetadata">
          <span>
            <span v-if="comic.bookmark">Read {{ comic.bookmark }} of </span
            >{{ comic.page_count }} Pages
            <span v-if="comic.finished">, Finished</span>
          </span>
          <span id="size">
            {{ comic.size | bytes }}
          </span>
        </span>

        <MetadataTextField
          :show="editMode"
          :value="comic.format"
          label="Format"
        />
        <MetadataCombobox
          :show="editMode"
          :model="comic.country"
          label="Country"
        />
        <MetadataCombobox
          :show="editMode"
          :model="comic.language"
          label="Language"
        />
        <a
          v-if="comic.web && !editMode"
          id="webLink"
          :href="comic.web"
          target="_blank"
        >
          <MetadataTextField
            :show="editMode"
            :value="comic.web"
            label="Web Link"
          />
        </a>
        <MetadataTextField
          v-else-if="editMode"
          :show="editMode"
          :value="comic.web"
          label="Web Link"
        />
        <MetadataTextField
          :show="editMode"
          :value="comic.user_rating"
          label="User Rating"
        />
        <MetadataTextField
          :show="editMode"
          :value="comic.critical_rating"
          label="Critical Rating"
        />
        <MetadataTextField
          :show="editMode"
          :value="comic.maturity_rating"
          label="Maturity Rating"
        />
        <MetadataTags :show="editMode" :tags="comic.genres" label="Genres" />
        <MetadataTags :show="editMode" :tags="comic.tags" label="Tags" />
        <MetadataTags :show="editMode" :tags="comic.teams" label="Teams" />
        <MetadataTags
          :show="editMode"
          :tags="comic.characters"
          label="Characters"
        />
        <MetadataTags
          :show="editMode"
          :tags="comic.locations"
          label="Locations"
        />
        <MetadataTags
          :show="editMode"
          :tags="comic.story_arcs"
          label="Story Arcs"
        />
        <MetadataTags
          :show="editMode"
          :tags="comic.series_groups"
          label="Series Groups"
        />
        <MetadataTextField :show="editMode" :value="comic.scan" label="Scan" />
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
          v-if="comic.credits && comic.credits.length > 0"
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
            <tr v-for="credit in comic.credits" :key="credit.pk">
              <td>
                <MetadataAutocomplete :model="credit.role.name" />
              </td>
              <td>
                <MetadataCombobox :model="credit.person.name" />
              </td>
            </tr>
          </tbody>
        </table>
        <div>
          <MetadataSwitch
            class="ltrSwitch"
            :value="comic.read_ltr"
            :label="ltrLabel"
            :readonly="true"
          />
          <MetadataSwitch
            class="editModeSwitch"
            :value="editMode"
            label="Edit Mode"
            @input="editMode = $event"
          />
        </div>
      </div>
      <footer id="footerLinks">
        <v-btn id="downloadButton" :href="downloadURL" download title="Download"
          ><v-icon>{{ mdiDownload }}</v-icon></v-btn
        >
        <v-btn v-if="isBrowser" :to="readerRoute" title="Read">
          <v-icon>{{ mdiEye }}</v-icon>
        </v-btn>
        <v-btn
          id="bottomCloseButton"
          ripple
          title="Close Metadata (esc)"
          @click="dialog = false"
          >x</v-btn
        >
      </footer>
    </div>
  </v-dialog>
</template>
<script>
import { mdiBorderColor, mdiDownload, mdiEye } from "@mdi/js";
import { mapState } from "vuex";

import { getDownloadURL } from "@/api/metadata";
import BookCover from "@/components/book-cover";
import MetadataAutocomplete from "@/components/metadata-autocomplete";
import MetadataCombobox from "@/components/metadata-combobox";
import MetadataSwitch from "@/components/metadata-switch";
import MetadataTags from "@/components/metadata-tags";
import MetadataTextField from "@/components/metadata-text-field";
import MetadataTextArea from "@/components/metadata-textarea";
import { getReaderRoute } from "@/router/route";

export default {
  name: "MetadataButton",
  components: {
    BookCover,
    MetadataAutocomplete,
    MetadataCombobox,
    MetadataSwitch,
    MetadataTags,
    MetadataTextArea,
    MetadataTextField,
  },
  props: {
    pk: {
      type: Number,
      required: true,
      default: 0,
    },
  },
  data() {
    return {
      mdiBorderColor,
      mdiDownload,
      mdiEye,
      dialog: false,
      editMode: false,
    };
  },
  computed: {
    ...mapState("metadata", {
      comic: (state) => state.comic,
    }),
    isBrowser: function () {
      return this.$route.name === "browser";
    },
    downloadURL: function () {
      return getDownloadURL(this.comic.pk);
    },
    readerRoute: function () {
      return getReaderRoute(this.comic);
    },
    ltrLabel: function () {
      let label = "Read ";
      if (this.comic.read_ltr) {
        label += "Left to Right";
      } else {
        label += "Right to Left";
      }
      return label;
    },
  },
  methods: {
    metadataOpened: function (pk) {
      this.$store.dispatch("metadata/comicMetadataOpened", pk);
    },
  },
};
</script>

<style scoped lang="scss">
@import "~vuetify/src/styles/styles.sass";
/*
#metadataContainer {
}
*/
#topCloseButton {
  float: right;
}
#bookCover {
  display: inline-block;
  float: left;
  margin-right: 15px;
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
.ltrSwitch,
.editModeSwitch {
  display: inline-block !important;
}
.editModeSwitch {
  float: right;
  visibility: hidden;
}
#dateRow {
  margin-right: 1em;
}
.datePicker {
  width: 80px;
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
#bottomCloseButton {
  float: right;
}
.halfWidth {
  display: inline-block;
}
#size {
  padding-left: 1em;
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
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  /*
  .v-dialog--fullscreen {
    padding: 15px !important;
  }
*/
}
</style>
<!-- eslint-enable vue-scoped-css/require-scoped -->
