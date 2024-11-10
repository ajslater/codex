<template>
  <section id="controls">
    <section id="controlRow">
      <DownloadButton
        id="downloadButton"
        class="controlButton"
        :button="true"
        :group="downloadGroup"
        :pks="downloadPks"
        :children="md.childCount"
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
import { mapActions, mapGetters, mapState } from "pinia";

import DownloadButton from "@/components/download-button.vue";
import MarkReadButton from "@/components/mark-read-button.vue";
import { NUMBER_FORMAT } from "@/datetime";
import { getReaderRoute } from "@/route";
import { useMetadataStore } from "@/stores/metadata";

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
    downloadGroup() {
      return this.md.group;
    },
    downloadPks() {
      return this.md.ids;
    },
    downloadNames() {
      const md = this.md;
      if (!md) {
        return ["Unknown.cbz"];
      } else if (md.fileName) {
        return [md.fileName];
      } else {
        return [
          this.firstNameFromList(md.publisherList),
          this.firstNameFromList(md.imprintList),
          this.firstNameFromList(md.seriesList),
          this.firstNameFromList(md.volumeList),
          this.md.name,
        ];
      }
    },
    isReadButtonShown() {
      return this.group === "c" && this.$route.name != "reader";
    },
    isReadButtonEnabled() {
      return Boolean(this.readerRoute);
    },
    markReadItem() {
      return {
        group: this.md.group,
        ids: this.md.ids,
        finished: this.md.finished,
        name: this.downloadNames,
        children: this.md.childCount,
      };
    },
    month() {
      if (!this.md.month) {
        return "";
      }
      const date = new Date(1970, this.md.month, 1);
      return date.toLocaleString("default", { month: "long" });
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
      if (list) {
        for (const obj of Object.values(list)) {
          if (obj.name) {
            name = obj.name;
            break;
          }
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
