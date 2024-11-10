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
      <MetadataHeader :group="group" :children="children" />
      <div id="metadataBody">
        <section class="mdSection">
          <MetadataText :value="md.summary" label="Summary" :maxHeight="100" />
          <MetadataText :value="md.review" label="Review" :maxHeight="100" />
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
import { mdiTagOutline } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";
import prettyBytes from "pretty-bytes";

import CloseButton from "@/components/close-button.vue";
import MetadataContributorsTable from "@/components/metadata/contributors-table.vue";
import MetadataHeader from "@/components/metadata/metadata-header.vue";
import MetadataTags from "@/components/metadata/metadata-tags.vue";
import MetadataText from "@/components/metadata/metadata-text.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { getDateTime } from "@/datetime";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

// Progress circle
// Can take 19 seconds for 22k children on huge collections
const CHILDREN_PER_SECOND = 1160;
const MIN_SECS = 0.05;
const UPDATE_INTERVAL = 250;
const SERIES_ROW_LARGE_LIMIT = 4;

export default {
  name: "MetadataButton",
  components: {
    CloseButton,
    MetadataContributorsTable,
    MetadataHeader,
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
      mdiTagOutline,
      dialog: false,
      progress: 0,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings?.twentyFourHourTime,
      readingDirectionTitles: (state) => state.choices.static.readingDirection,
      identifierTypes: (state) => state.choices.static.identifierType,
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
    readingDirectionText() {
      if (!this.md) {
        return "Unknown";
      }
      return this.readingDirectionTitles[this.md.readingDirection];
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

#placeholderContainer {
  min-height: 100%;
  min-width: 100%;
  text-align: center;
}

#placeholderTitle {
  font-size: xx-large;
  color: rgb(var(--v-theme-textDisabled));
}

.inlineRow>* {
  display: inline-flex;
}

.mdSection {
  margin-top: 25px;
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

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #metadataContainer {
    font-size: 12px;
  }
}
</style>
