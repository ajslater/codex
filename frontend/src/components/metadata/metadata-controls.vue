<template>
  <section class="controlRow">
    <DownloadButton
      id="downloadButton"
      :button="true"
      :item="downloadItem"
      :size="size"
    />
    <MarkReadButton
      id="markReadButton"
      :button="true"
      :item="markReadItem"
      :size="size"
    />
    <FavoriteToggle
      v-if="favoritePk"
      id="favoriteButton"
      :group="group"
      :pk="favoritePk"
    />
    <v-btn
      v-if="isReadButtonShown"
      id="readButton"
      title="Read Comic"
      :disabled="!isReadButtonEnabled"
      :size="size"
      :to="readerRoute"
    >
      <v-icon>{{ readButtonIcon }}</v-icon>
      Read
    </v-btn>
    <OnlineTagLauncherDialog
      v-if="isUserAdmin"
      :book="controlBook"
      :size="size"
      @started="$emit('onlineTagStarted')"
    />
    <v-btn
      v-if="isUserAdmin"
      variant="tonal"
      :size="size"
      @click="$emit('editTags')"
    >
      Edit Tags
    </v-btn>
  </section>
</template>

<script>
import { mdiEye, mdiEyeOff } from "@mdi/js";
import { mapState } from "pinia";

import { formattedIssue } from "@/comic-name";
import DownloadButton from "@/components/download-button.vue";
import FavoriteToggle from "@/components/favorite-toggle.vue";
import MarkReadButton from "@/components/mark-read-button.vue";
import OnlineTagLauncherDialog from "@/components/online-tag/launcher-dialog.vue";
import { getReaderRoute } from "@/route";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

const GROUP_MAP = Object.freeze({
  p: "publisher",
  i: "imprint",
  s: "series",
  v: "volume",
  f: "folder",
  a: "storyArc",
});

export default {
  name: "MetadataControls",
  components: {
    DownloadButton,
    FavoriteToggle,
    MarkReadButton,
    OnlineTagLauncherDialog,
  },
  props: {
    group: {
      type: String,
      required: true,
    },
    book: {
      type: Object,
      default: null,
    },
  },
  emits: ["editTags", "onlineTagStarted"],
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
    }),
    ...mapState(useBrowserStore, {
      importMetadata: (state) => state.page?.adminFlags?.importMetadata,
    }),
    downloadName() {
      const md = this.md;
      let name;
      if (!md) {
        name = "Unknown.cbz";
      } else if (md.fileName) {
        name = md.fileName;
      } else {
        if (this.md.collection === "folders") {
          return [this.firstNameFromList(md.folderList)];
        }
        if (this.md.collection === "arcs") {
          return [this.firstNameFromList(md.storyArcList)];
        }
        const names = [
          this.firstNameFromList(md.publisherList),
          this.firstNameFromList(md.imprintList),
          this.firstNameFromList(md.seriesList),
          this.firstNameFromList(md.volumeList),
          formattedIssue(this.md, 3),
          this.md.name,
        ];
        name = names.filter(Boolean).join(" ");
      }
      return name;
    },
    downloadItem() {
      return {
        group: this.md?.collection,
        ids: this.md?.ids,
        childCount: this.md?.childCount,
        mtime: this.md?.mtime,
        name: this.downloadName,
      };
    },
    isReadButtonShown() {
      return this.group === "comics" && this.$route.name != "reader";
    },
    favoritePk() {
      /*
       * The metadata header only renders this control row when a
       * single-target view is active, so ``ids`` will normally be a
       * one-element list. The toggle drives a single backend row, so
       * hide the star for any unexpected multi-id payload rather
       * than guessing which target to write.
       */
      const ids = this.md?.ids;
      if (!Array.isArray(ids) || ids.length !== 1) return undefined;
      return ids[0];
    },
    isReadButtonEnabled() {
      return Boolean(this.readerRoute);
    },
    markReadItem() {
      let name = "";
      const prefix = GROUP_MAP[this.md.collection];
      if (prefix) {
        const nameList = this.md[prefix + "List"] || [];
        const names = nameList.map(({ name }) => name);
        name = names.join(", ");
      } else {
        name = this.md.name;
      }
      return {
        group: this.md.collection,
        ids: this.md.ids,
        finished: this.md.finished,
        name,
        children: this.md.childCount || 1,
      };
    },
    readButtonIcon() {
      return this.isReadButtonEnabled ? mdiEye : mdiEyeOff;
    },
    readerRoute() {
      return this.md?.ids ? getReaderRoute(this.md, this.importMetadata) : {};
    },
    controlBook() {
      return (
        this.book || {
          group: this.md?.collection,
          pk: this.md?.ids?.[0],
          ids: this.md?.ids,
          childCount: this.md?.childCount,
        }
      );
    },
    size() {
      return this.$vuetify.display.smAndDown ? "x-small" : "default";
    },
  },
  methods: {
    firstNameFromList(list) {
      let name = "";
      if (!list) {
        return name;
      }
      for (const obj of Object.values(list)) {
        if (obj.name) {
          name = obj.name;
          break;
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

.controlRow > * {
  margin-right: 10px;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .controlRow > * {
    margin-right: 1px;
  }
}
</style>
