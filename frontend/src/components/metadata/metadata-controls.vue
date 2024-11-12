<template>
  <section id="controls">
    <section id="controlRow">
      <DownloadButton
        id="downloadButton"
        class="controlButton"
        :button="true"
        :group="downloadGroup"
        :pks="downloadPks"
        :children="md?.childCount || 1"
        :names="downloadNames"
        :ts="md.mtime"
      />
      <MarkReadButton
        id="markReadButton"
        class="controlButton"
        :button="true"
        :item="markReadItem"
      />
      <v-btn
        v-if="isReadButtonShown"
        id="readButton"
        class="controlButton"
        :to="readerRoute"
        title="Read Comic"
        :disabled="!isReadButtonEnabled"
      >
        <v-icon>{{ readButtonIcon }}</v-icon>
        Read
      </v-btn>
    </section>
  </section>
</template>

<script>
import { mdiEye, mdiEyeOff } from "@mdi/js";
import { mapActions, mapGetters, mapState } from "pinia";

import { formattedIssue, formattedVolumeName } from "@/comic-name";
import DownloadButton from "@/components/download-button.vue";
import MarkReadButton from "@/components/mark-read-button.vue";
import { NUMBER_FORMAT } from "@/datetime";
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
    downloadGroup() {
      return this.md.group;
    },
    downloadPks() {
      return this.md.ids;
    },
    downloadNames() {
      const md = this.md;
      let names = [];
      if (!md) {
        names = ["Unknown.cbz"];
      } else if (md.fileName) {
        names = [md.fileName];
      } else {
        if (this.md.group === "f") {
          return [this.firstNameFromList(md.folderList)];
        }
        if (this.md.group === "a") {
          return [this.firstNameFromList(md.storyArcList)];
        }
        names = [
          this.firstNameFromList(md.publisherList),
          this.firstNameFromList(md.imprintList),
          this.firstNameFromList(md.seriesList),
          this.firstNameFromList(md.volumeList),
        ];
        const issue = formattedIssue(this.md, 3);
        if (issue) {
          names.push(issue);
        }
        names.push(this.md.name);
      }
      return names;
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
        children: this.md.childCount,
      };
    },
    readButtonIcon() {
      return this.isReadButtonEnabled ? mdiEye : mdiEyeOff;
    },
    readerRoute() {
      if (this.md?.ids) {
        return getReaderRoute(this.md, this.importMetadata);
      } else {
        return {};
      }
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

#controls {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  margin-top: 4px;
}

.controlButton {
  margin-right: 10px;
}
</style>
