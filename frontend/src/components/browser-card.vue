<template>
  <v-lazy transition="scale-transition" class="browserTile">
    <div class="browserTileLazyWrapper">
      <div class="browserCardCoverWrapper">
        <BookCover
          :cover-path="item.cover_path"
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
        <div v-if="headerName" class="headerName">{{ headerName }}</div>
        <div class="displayName">{{ displayName }}</div>
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div v-if="orderValue" class="orderValue" v-html="orderValue" />
      </router-link>
    </div>
  </v-lazy>
</template>

<script>
// import { mdiChevronLeft } from "@mdi/js";
import { mdiEye } from "@mdi/js";
import filesize from "filesize";
import { mapState } from "vuex";

import BookCover from "@/components/book-cover";
import BrowserCardMenu from "@/components/browser-card-menu";
import {
  getFullComicName,
  getIssueName,
  getVolumeName,
} from "@/components/comic-name";
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
      mdiEye,
    };
  },
  // Stored here instead of data to be non-reactive
  orderByCache: "sort_name",
  computed: {
    ...mapState("browser", {
      orderBy: (state) => state.settings.orderBy,
    }),
    headerName: function () {
      let headerName;
      switch (this.item.group) {
        case "c":
          headerName =
            !Number(this.$route.params.pk) || this.$route.params.group === "f"
              ? (headerName = getFullComicName(
                  this.item.series_name,
                  this.item.volume_name,
                  Number(this.item.issue)
                ))
              : (headerName = getIssueName(this.item.issue));
          break;

        case "i":
          headerName = this.item.publisher_name;
          break;

        case "v":
          headerName = this.item.series_name;
          break;

        default:
          headerName = "";
      }
      return headerName;
    },
    displayName: function () {
      return this.item.group === "v"
        ? getVolumeName(this.item.name)
        : this.item.name;
    },
    orderValue: function () {
      let ov = this.item.order_value;
      if (
        this.orderByCache === "sort_name" ||
        this.orderByCache === null ||
        this.orderByCache === undefined ||
        ov === null ||
        ov === undefined
      ) {
        ov = "";
      } else if (this.orderByCache == "page_count") {
        const human = filesize(Number.parseInt(ov, 10), {
          base: 10,
          round: 1,
          fullform: true,
          fullforms: [" ", "K", "M", "G", "T", "P", "E", "Z", "Y"],
          spacer: "",
        });
        ov = `${human} pages`;
      } else if (this.orderByCache == "size") {
        ov = filesize(Number.parseInt(ov, 10), { round: 1 });
      } else if (STAR_SORT_BY.has(this.orderByCache)) {
        ov = `${ov} stars`;
      } else if (DATE_SORT_BY.has(this.orderByCache)) {
        ov = this.formatDate(ov, false);
      } else if (TIME_SORT_BY.has(this.orderByCache)) {
        ov = this.formatDate(ov, true);
      }
      return ov;
    },
    toRoute: function () {
      return this.item.group === "c"
        ? getReaderRoute(
            this.item.pk,
            this.item.bookmark,
            this.item.read_ltr,
            this.item.page_count
          )
        : {
            name: "browser",
            params: { group: this.item.group, pk: this.item.pk, page: 1 },
          };
    },
  },
  watch: {
    orderBy: function (to) {
      this.orderByCache = to;
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
