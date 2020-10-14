<template>
  <v-lazy transition="scale-transition" class="browserTile">
    <div class="browserTileLazyWrapper">
      <div class="browserCardCoverWrapper">
        <BookCover
          :cover-path="item.x_cover_path"
          :group="item.group"
          :child-count="item.child_count"
          :finished="item.finished"
        />
        <div class="cardCoverOverlay">
          <router-link class="browserLink" :to="toRoute">
            <div class="cardCoverOverlayTopMiddleRow">
              <v-icon v-if="item.group === 'c'">{{ mdiEye }}</v-icon>
            </div>
          </router-link>
          <div class="cardCoverOverlayBottomRow">
            <MetadataButton
              class="metadataButton"
              :group="item.group"
              :pk="item.pk"
              :children="item.child_count"
            />
            <BrowserCardMenu
              class="browserCardMenu"
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
      <router-link class="browserLink cardSubtitle text-caption" :to="toRoute">
        <div class="headerName">{{ headerName }}</div>
        <div class="displayName">{{ displayName }}</div>
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div class="orderValue" v-html="orderValue" />
      </router-link>
    </div>
  </v-lazy>
</template>

<script>
// import { mdiChevronLeft } from "@mdi/js";
import { mdiDotsVertical, mdiEye } from "@mdi/js";
import filesize from "filesize";
import { mapState } from "vuex";

import BookCover from "@/components/book-cover";
import BrowserCardMenu from "@/components/browser-card-menu";
import { getFullComicName, getVolumeName } from "@/components/comic-name";
import MetadataButton from "@/components/metadata-dialog";
import { getReaderRoute } from "@/router/route";

const STAR_SORT_BY = new Set(["user_rating", "critical_rating"]);
const DATE_SORT_BY = new Set(["date"]);
const TIME_SORT_BY = new Set(["created_at", "updated_at"]);

export default {
  name: "BrowserCard",
  components: {
    BookCover,
    BrowserCardMenu,
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
    headerName: function () {
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
    displayName: function () {
      let displayName;
      if (this.item.group === "v") {
        displayName = getVolumeName(this.item.display_name);
      } else {
        displayName = this.item.display_name;
      }
      return displayName;
    },
    orderValue: function () {
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
      } else if (STAR_SORT_BY.has(this.sortBy)) {
        return `${ov} stars`;
      } else if (DATE_SORT_BY.has(this.sortBy)) {
        return this.formatDate(ov, false);
      } else if (TIME_SORT_BY.has(this.sortBy)) {
        return this.formatDate(ov, true);
      } else {
        return ov;
      }
    },
    toRoute: function () {
      if (this.item.group === "c") {
        return getReaderRoute(
          this.item.pk,
          this.item.bookmark,
          this.item.read_ltr,
          this.item.page_count
        );
      } else {
        return {
          name: "browser",
          params: { group: this.item.group, pk: this.item.pk, page: 1 },
        };
      }
    },
  },
  methods: {
    formatDate: function (ov, time) {
      const date = new Date(ov);
      const year = `${date.getFullYear()}`.padStart(4, "0");
      const month = `${date.getMonth() + 1}`.padStart(2, "0");
      const day = `${date.getDate()}`.padStart(2, "0");
      let result = [year, month, day].join("-");
      if (time) {
        result += "<br />" + date.toLocaleTimeString("en-US");
      }
      return result;
    },
  },
};
</script>

<style scoped lang="scss">
@import "~vuetify/src/styles/styles.sass";
.browserTile {
  display: inline-flex;
  flex: 1;
  margin: 16px;
  width: 120px;
  text-align: center;
}
.browserCardCoverWrapper {
  position: relative;
}
.cardCoverOverlay {
  position: absolute;
  top: 0px;
  height: 100%;
  width: 100%;
  text-align: center;
  border-radius: 5px;
  border: solid thin transparent;
}
.browserCardCoverWrapper:hover > .cardCoverOverlay {
  background-color: rgba(0, 0, 0, 0.5);
  border: solid thin #cc7b19;
}
.cardCoverOverlay > * {
  width: 100%;
}
.browserCardCoverWrapper:hover > .cardCoverOverlay * {
  /* optimize-css-assets-webpack-plugin / cssnano bug destroys % values. 
     use decimals instead.
     https://github.com/NMFR/optimize-css-assets-webpack-plugin/issues/118
  */
  opacity: 1;
}
.cardCoverOverlayTopMiddleRow {
  height: 70%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cardCoverOverlayTopMiddleRow,
.cardCoverOverlayBottomRow {
  opacity: 0;
}
.cardCoverOverlayBottomRow {
  height: 15%;
  display: flex;
  position: absolute;
  bottom: 0px;
}
.browserLink {
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
.metadataButton {
  position: absolute;
  bottom: 5px;
  left: 5px;
}

@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .browserTile {
    margin: 8px;
    width: 100px;
  }
}
</style>
