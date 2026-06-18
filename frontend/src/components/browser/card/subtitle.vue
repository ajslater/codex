<template>
  <div class="browserLink cardSubtitle text-caption">
    <div v-if="fileName" class="fileName">
      {{ fileName }}
    </div>
    <div v-if="seriesName" class="seriesCaption">
      {{ seriesName }}
    </div>
    <div v-if="volumeName" class="volumeCaption">
      {{ volumeName }}
    </div>
    <div v-if="headerName" class="headerName">
      {{ headerName }}
    </div>
    <div v-if="item.collectionTitle">
      {{ item.collectionTitle }}
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
      orderByFilename: (state) => state.settings.orderBy === "filename",
      orderByName: (state) => state.settings.orderBy === "sort_name",
      topCollection: (state) => state.settings.topCollection,
      showSeries: (state) => state.settings.show["series"],
      showVolume: (state) => state.settings.show["volumes"],
      zeroPad: (state) => state.page.zeroPad,
      alwaysShowFilename: (state) => state.settings.alwaysShowFilename,
    }),
    seriesName() {
      if (
        (this.topCollection === "arcs" ||
          (this.orderByName && !this.showSeries)) &&
        ["comics", "volumes"].includes(this.item.collection) &&
        this.item.seriesName
      ) {
        return this.item.seriesName;
      }
      return false;
    },
    volumeName() {
      if (
        (this.topCollection === "arcs" ||
          (this.orderByName && !this.showVolume)) &&
        this.item.collection === "comics" &&
        this.item.volumeName
      ) {
        return formattedVolumeName(
          this.item.volumeName,
          this.item.volumeNumberTo,
        );
      }
      return false;
    },
    headerName() {
      let hn;
      switch (this.item.collection) {
        case "imprints":
          hn = this.item.publisherName;
          break;
        case "volumes":
          hn = this.item.seriesName;
          break;
        case "comics":
          hn =
            this.$route.params.collection === "folders"
              ? getFullComicName(this.item, this.zeroPad)
              : getIssueName(this.item, this.zeroPad);
          break;
        default:
          hn = "";
      }
      if (hn && this.item.ids && this.item.ids.length > 1) {
        return "(Multiple)";
      }
      return hn;
    },
    displayName() {
      return this.item.collection === "volumes"
        ? formattedVolumeName(this.item.name, this.item.numberTo)
        : this.item.name;
    },
    fileName() {
      return !this.orderByFilename &&
        (this.alwaysShowFilename || this.topCollection === "folders")
        ? this.item.fileName
        : "";
    },
    linkLabel() {
      let label = "";
      label += this.item.collection === "comics" ? "Read" : "Browse to";
      label += " " + this.headerName;
      return label;
    },
  },
};
</script>

<style scoped lang="scss">
.cardSubtitle {
  width: 100%;
  text-align: center;
  overflow-wrap: anywhere;
}

.seriesCaption,
.volumeCaption {
  color: rgb(var(--v-theme-textDisabled));
  text-align: center;
}

.headerName {
  padding-top: 5px;
  color: rgb(var(--v-theme-textDisabled));
}

.displayName {
  min-height: 1em;
}
</style>
