<template>
  <div class="browserLink cardSubtitle text-caption">
    <div v-if="seriesName" class="seriesCaption">{{ seriesName }}</div>
    <div v-if="volumeName" class="volumeCaption">{{ volumeName }}</div>
    <div v-if="headerName" class="headerName">
      {{ headerName }}
    </div>
    <div class="displayName">
      {{ displayName }}
    </div>
  </div>
</template>

<script>
import { mapState } from "pinia";

import {
  formattedVolumeName,
  getFullComicName,
  getIssueName,
} from "@/comic-name";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserCardSubtitle",
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapState(useBrowserStore, {
      orderByName: (state) => state.settings.orderBy == "sort_name",
      topGroup: (state) => state.settings.topGroup,
      showSeries: (state) => state.settings.show["s"],
      showVolume: (state) => state.settings.show["v"],
      zeroPad: (state) => state.page.zeroPad,
    }),
    seriesName() {
      if (
        (this.topGroup === "a" || (this.orderByName && !this.showSeries)) &&
        ["c", "v"].includes(this.item.group) &&
        this.item.seriesName
      ) {
        return this.item.seriesName;
      }
      return false;
    },
    volumeName() {
      if (
        (this.topGroup === "a" || (this.orderByname && !this.showVolume)) &&
        this.item.group === "c" &&
        this.item.volumeName
      ) {
        return formattedVolumeName(this.item.volumeName);
      }
      return false;
    },
    headerName: function () {
      let hn;
      switch (this.item.group) {
        case "i":
          hn = this.item.publisherName;
          break;

        case "v":
          hn = this.item.seriesName;
          break;
        case "c":
          hn =
            this.$route.params.group === "f"
              ? getFullComicName(this.item, this.zeroPad)
              : getIssueName(this.item, this.zeroPad);
          break;
        default:
          hn = "";
      }
      return hn;
    },
    displayName: function () {
      return this.item.group === "v"
        ? formattedVolumeName(this.item.name)
        : this.item.name;
    },
    linkLabel: function () {
      let label = "";
      label += this.item.group === "c" ? "Read" : "Browse to";
      label += " " + this.headerName;
      return label;
    },
  },
};
</script>

<style scoped lang="scss">
.cardSubtitle {
  width: 100%;
  margin-top: 10px;
  text-align: center;
}
.seriesCaption, .volumeCaption {
  color: rgb(var(--v-theme-textDisabled));
  text-align: center;
}
.headerName {
  padding-top: 5px;
  color: rgb(var(--v-theme-textDisabled));
}
.headerName,
.displayName {
  overflow-wrap: break-word;
}
.displayName {
  min-height: 1em;
}
</style>
