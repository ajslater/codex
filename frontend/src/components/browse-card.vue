<template>
  <div class="browseTile">
    <div class="browseTileContent">
      <div class="coverWrapper">
        <BookCover :cover-path="item.x_cover_path" :progress="+item.progress" />
        <div
          v-if="!item.finished"
          class="unreadFlag"
          :class="{ mixedreadFlag: item.finished === null }"
        />
        <div class="coverOverlay">
          <router-link class="browseLink" :to="getToRoute()">
            <div class="coverOverlayTopRow">
              <span v-if="item.child_count" class="childCount">
                {{ item.child_count }}
              </span>
            </div>
            <div class="coverOverlayMiddleRow">
              <v-icon v-if="item.group === 'c'">{{ mdiEye }}</v-icon>
            </div>
          </router-link>
          <div class="coverOverlayBottomRow">
            <MetadataButton
              v-if="item.group === 'c'"
              class="metadataButton"
              :pk="item.pk"
            />
            <BrowseContainerMenu
              :group="item.group"
              :pk="item.pk"
              :finished="item.finished"
            />
          </div>
        </div>
      </div>
      <v-progress-linear
        class="bookCoverProgress"
        :value="item.progress"
        rounded
        background-color="inherit"
        height="2"
      />
      <router-link
        class="browseLink cardSubtitle text-caption"
        :to="getToRoute()"
      >
        <div class="headerName">
          {{ getHeaderName() }}
        </div>
        <div class="displayName">
          {{ getDisplayName() }}
        </div>
        <div class="orderValue">
          {{ getOrderValue() }}
        </div>
      </router-link>
    </div>
  </div>
</template>

<script>
// import { mdiChevronLeft } from "@mdi/js";
import { mdiDotsVertical, mdiEye } from "@mdi/js";
import filesize from "filesize";
import { mapState } from "vuex";

import { getFullComicName, getVolumeName } from "@/comic-name";
import BookCover from "@/components/book-cover";
import BrowseContainerMenu from "@/components/browse-container-menu";
import MetadataButton from "@/components/metadata-dialog";
import { getReaderRoute } from "@/router/route";

export default {
  name: "BrowseCard",
  components: {
    BookCover,
    BrowseContainerMenu,
    MetadataButton,
  },
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      mdiDotsVertical,
      mdiEye,
    };
  },
  computed: {
    ...mapState("browser", {
      sortBy: (state) => state.settings.sortBy,
    }),
  },
  methods: {
    getToRoute: function () {
      if (this.item.group === "c") {
        return getReaderRoute(this.item);
      } else {
        return {
          name: "browser",
          params: { group: this.item.group, pk: this.item.pk, page: 1 },
        };
      }
    },
    markRead: function (group, pk, finished) {
      this.$store.dispatch("browser/markRead", { group, pk, finished });
    },
    getHeaderName: function () {
      let headerName;
      if (this.item.group === "c") {
        return getFullComicName(
          this.item.series_name,
          this.item.volume_name,
          +this.item.x_issue
        );
      } else {
        headerName = this.item.header_name;
      }
      return headerName;
    },
    getDisplayName: function () {
      let displayName;
      if (this.item.group === "v") {
        displayName = getVolumeName(this.item.display_name);
      } else {
        displayName = this.item.display_name;
      }
      return displayName;
    },
    getOrderValue: function () {
      let ov = this.item.order_value;
      if (this.sortBy == "sort_name" || !ov) {
        return "";
      } else if (this.sortBy == "page_count") {
        const human = filesize(parseInt(ov), {
          base: 10,
          round: 1,
          fullform: true,
          fullforms: [" ", "K", "M", "G", "T", "P", "E", "Z", "Y"],
          spacer: "",
        });
        return `${human} pages`;
      } else if (this.sortBy == "size") {
        return filesize(parseInt(ov), { round: 1 });
      } else if (["user_rating", "critical_rating"].includes(this.sortBy)) {
        return `${ov} stars`;
      } else if (["created_at"].includes(this.sortBy)) {
        const date = new Date(ov);
        const year = `${date.getFullYear()}`.padStart(4, "0");
        const month = `${date.getMonth() + 1}`.padStart(2, "0");
        const day = `${date.getDate()}`.padStart(2, "0");
        return [year, month, day].join("-");
      } else {
        return ov;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@import "~vuetify/src/styles/styles.sass";
.browseTile {
  float: left;
  padding: 16px;
  text-decoration: none;
  text-align: center;
}
.browseTileContent {
  height: 250px;
  width: 120px;
}
.coverWrapper {
  position: relative;
}
.coverOverlay {
  position: absolute;
  top: 0px;
  height: 100%;
  width: 100%;
  text-align: center;
  border-radius: 5px;
  border: solid thin transparent;
}
.coverWrapper:hover > .coverOverlay {
  background-color: rgba(0, 0, 0, 0.5);
  border: solid thin #cc7b19;
}
.coverOverlay > * {
  width: 100%;
}
.coverWrapper:hover > .coverOverlay * {
  /* optimize-css-assets-webpack-plugin / cssnano bug destroys % values. 
     use decimals instead.
     https://github.com/NMFR/optimize-css-assets-webpack-plugin/issues/118
  */
  opacity: 1;
}
.coverOverlayTopRow,
.coverOverlayBottomRow {
  height: 15%;
}
.coverOverlayTopRow {
  display: flex;
  opacity: 1;
}
.coverOverlayMiddleRow {
  height: 70%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.coverOverlayMiddleRow,
.coverOverlayBottomRow {
  opacity: 0;
}
.coverOverlayBottomRow {
  display: flex;
}
.childCount {
  position: absolute;
  top: 0;
  left: 0;
  display: inline;
  min-width: 1.5rem;
  padding: 0rem 0.25rem 0rem 0.25rem;
  border-radius: 50%;
  background-color: black;
  color: white;
}
.unreadFlag {
  position: absolute;
  top: 0;
  right: 0;
  display: block;
  width: 24px;
  height: 24px;
  background: linear-gradient(
    45deg,
    transparent 50%,
    rgba(0, 0, 0, 0.5) 60%,
    var(--v-primary-base) 60%
  );
  border-radius: 5px;
}
.mixedreadFlag {
  background: linear-gradient(
    45deg,
    transparent 50%,
    rgba(0, 0, 0, 0.5) 60%,
    var(--v-primary-base) 60%,
    var(--v-primary-base) 70%,
    transparent 70%,
    rgba(0, 0, 0, 0.5) 80%,
    var(--v-primary-base) 80%,
    var(--v-primary-base) 90%,
    transparent 90%
  );
}
.metadataButton {
  position: absolute;
  bottom: 3px;
  left: 3px;
}
.browseLink {
  text-decoration: none;
  color: inherit;
}
.bookCoverProgress {
  margin-top: 1px;
}
.cardSubtitle {
  margin-top: 7px;
  padding-top: 3px;
}
.headerName {
  padding-top: 5px;
  color: gray;
}
.orderValue {
  color: gray;
}
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .browseTile {
    padding: 8px;
  }
  .browseTileContent {
    width: 100px;
  }
}
</style>
