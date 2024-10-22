<template>
  <v-btn v-if="show && !confirm && button" @click="download">
    <v-icon>
      {{ mdiDownload }}
    </v-icon>
    {{ title }}
  </v-btn>
  <CodexListItem
    v-else-if="show && !confirm"
    :prepend-icon="mdiDownload"
    :title="title"
    @click="download"
  />
  <ConfirmDialog
    v-else-if="show"
    :button="button"
    :prepend-icon="mdiDownload"
    :button-text="title"
    :title-text="title"
    text="May take a while"
    confirm-text="Download"
    @confirm="download"
  />
</template>
<script>
import { mdiDownload } from "@mdi/js";
import { mapGetters } from "pinia";

import { getGroupDownloadURL } from "@/api/v3/browser";
import { getDownloadIOSPWAFix } from "@/api/v3/common";
import { getComicDownloadURL } from "@/api/v3/reader";
import { topGroup as GROUP_NAME_MAP } from "@/choices/browser-map.json";
import CodexListItem from "@/components/codex-list-item.vue";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { NUMBER_FORMAT } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";

const CHILD_WARNING_LIMIT = 10;

export default {
  name: "DownloadButton",
  components: { ConfirmDialog, CodexListItem },
  props: {
    button: {
      type: Boolean,
      default: false,
    },
    group: {
      type: String,
      default: "c",
    },
    pks: {
      type: Array,
      required: true,
    },
    children: {
      type: Number,
      required: true,
    },
    names: {
      type: Array,
      required: true,
    },
    ts: {
      type: Number,
      default: undefined,
    },
  },
  data() {
    return { mdiDownload };
  },
  computed: {
    ...mapGetters(useBrowserStore, ["filterOnlySettings"]),
    show() {
      return this.pks && this.pks.length > 0 && !this.pks.includes(0);
    },
    isOneComic() {
      return this.group === "c" && this.pks.length === 1;
    },
    downloadURL() {
      let url = "";
      if (this.isOneComic) {
        const pk = this.pks[0];
        url = getComicDownloadURL({ pk }, this.downloadFn, this.ts);
      } else {
        const group = this.group;
        const pks = this.pks;
        const settings = this.filterOnlySettings;
        url = getGroupDownloadURL(
          { group, pks },
          this.downloadFn,
          settings,
          this.ts,
        );
      }
      return url;
    },
    formattedChildren() {
      return NUMBER_FORMAT.format(this.children);
    },
    downloadFn() {
      const name = this.names.filter((x) => x).join(" ");
      if (this.isOneComic) {
        return name;
      } else {
        let groupName = GROUP_NAME_MAP[this.group];
        if (groupName !== "Series") {
          groupName = groupName.slice(0, -1);
        }
        return `${groupName} - ${name} Comics.zip`;
      }
    },
    title() {
      let titleStr = "Download";
      if (this.isOneComic) {
        titleStr += " Book";
      } else {
        titleStr += ` ${this.formattedChildren} Books`;
      }
      return titleStr;
    },
    confirm() {
      return this.children > CHILD_WARNING_LIMIT;
    },
    confirmText() {
      return `Download ${this.formattedChildren} books`;
    },
  },
  methods: {
    download() {
      const url = this.downloadURL;
      const fn = this.downloadFn;
      if (this.isOneComic) {
        getDownloadIOSPWAFix(url, fn);
      } else {
        // Simple download does not go through iOS PWA Fix.
        const link = document.createElement("a");
        link.download = this.downloadFn;
        link.href = this.downloadURL;
        link.click();
        link.remove();
      }
    },
  },
};
</script>

<style scoped lang="scss">
:deep(.v-icon) {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
