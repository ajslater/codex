<template>
  <ConfirmDialog
    v-if="show"
    :button="button"
    :button-text="title"
    :confirm="confirm"
    confirm-text="Download"
    :prepend-icon="mdiDownload"
    :title-text="title"
    text="May take a while"
    @confirm="download"
  />
</template>
<script>
import { mdiDownload } from "@mdi/js";
import { mapState } from "pinia";

import { getGroupDownloadURL } from "@/api/v3/browser";
import { getDownloadIOSPWAFix } from "@/api/v3/common";
import { getComicDownloadURL } from "@/api/v3/reader";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { NUMBER_FORMAT } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";

const CHILD_WARNING_LIMIT = 10;

export default {
  name: "DownloadButton",
  components: { ConfirmDialog },
  props: {
    button: {
      type: Boolean,
      default: false,
    },
    item: {
      type: Object,
      required: true,
    },
  },
  data() {
    return { mdiDownload };
  },
  computed: {
    ...mapState(useBrowserStore, ["filterOnlySettings", "groupNames"]),
    show() {
      return this.item?.ids?.length > 0 && !this.item.ids.includes(0);
    },
    isOneComic() {
      return this.item?.group === "c" && this.item?.ids?.length === 1;
    },
    downloadFn() {
      if (this.isOneComic) {
        return this.item.name;
      } else {
        const groupName = this.groupNames[this.item?.group];
        return `${groupName} - ${this.item.name} Comics.zip`;
      }
    },
    downloadURL() {
      let url = "";
      if (this.isOneComic) {
        const pk = this.item.ids[0];
        url = getComicDownloadURL({ pk }, this.downloadFn, this.item?.mtime);
      } else {
        const group = this.item?.group;
        const pks = this.item?.ids;
        const settings = this.filterOnlySettings;
        url = getGroupDownloadURL(
          { group, pks },
          this.downloadFn,
          settings,
          this.item?.mtime,
        );
      }
      return url;
    },
    formattedChildren() {
      return NUMBER_FORMAT.format(this.item?.childCount);
    },
    title() {
      let titleStr = "Download";
      titleStr += this.isOneComic
        ? " Book"
        : ` ${this.formattedChildren} Books`;
      return titleStr;
    },
    confirm() {
      return this.item?.childCount > CHILD_WARNING_LIMIT;
    },
    confirmText() {
      if (!this.confirm) {
        return "";
      }
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
