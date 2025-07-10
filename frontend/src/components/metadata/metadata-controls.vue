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
  </section>
</template>

<script>
import { mdiEye, mdiEyeOff } from "@mdi/js";
import { mapState } from "pinia";

import { formattedIssue } from "@/comic-name";
import DownloadButton from "@/components/download-button.vue";
import MarkReadButton from "@/components/mark-read-button.vue";
import { getReaderRoute } from "@/route";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

const GROUP_MAP = {
  p: "publisher",
  i: "imprint",
  s: "series",
  v: "volume",
  f: "folder",
  a: "storyArc",
};
Object.freeze(GROUP_MAP);

export default {
  name: "MetadataControls",
  components: {
    DownloadButton,
    MarkReadButton,
  },
  props: {
    group: {
      type: String,
      required: true,
    },
  },
  computed: {
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
        if (this.md.group === "f") {
          return [this.firstNameFromList(md.folderList)];
        }
        if (this.md.group === "a") {
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
        group: this.md?.group,
        ids: this.md?.ids,
        childCount: this.md?.childCount,
        mtime: this.md?.mtime,
        name: this.downloadName,
      };
    },
    isReadButtonShown() {
      return this.group === "c" && this.$route.name != "reader";
    },
    isReadButtonEnabled() {
      return Boolean(this.readerRoute);
    },
    markReadItem() {
      let name = "";
      const prefix = GROUP_MAP[this.md.group];
      if (prefix) {
        const nameList = this.md[prefix + "List"] || [];
        const names = nameList.map(({ name }) => name);
        name = names.join(", ");
      } else {
        name = this.md.name;
      }
      return {
        group: this.md.group,
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
