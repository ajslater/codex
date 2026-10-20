<template>
  <v-toolbar id="browserToolbarTitle" :height="24" :extension-height="24">
    <v-toolbar-title id="browserTitle" class="browserTitle">
      {{ title }}
    </v-toolbar-title>
    <div v-if="titleBook" class="titleTagButton">
      <MetadataDialog
        :book="titleBook"
        toolbar
        size="small"
        density="compact"
      />
    </div>
    <template v-if="subtitle" #extension>
      <v-toolbar-title id="browserSubtitle" class="browserTitle">
        {{ subtitle }}
      </v-toolbar-title>
    </template>
  </v-toolbar>
</template>

<script>
import { mdiReload } from "@mdi/js";
import { mapState } from "pinia";

import { formattedVolumeName, formattedYearRange } from "@/comic-name";
import MetadataDialog from "@/components/metadata/metadata-dialog.vue";
import { collectionForRoute } from "@/route";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserHeader",
  components: {
    MetadataDialog,
  },
  data() {
    return {
      mdiReload,
    };
  },
  head() {
    const titleSuffix = this.subtitle ? this.subtitle : this.title;
    const title = "Browse / " + titleSuffix;
    const names = ["browse comics", this.title, this.subtitle];
    const content = names.filter(Boolean).join(" ");
    return {
      title,
      meta: [{ name: "description", content }],
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      browserTitle: (state) => state.page?.title,
      collectionNames: (state) => state.choices.static.collectionNames,
      modelCollection: (state) => state.page.modelCollection,
    }),
    ...mapState(useAuthStore, ["isUserAdmin"]),
    routeTarget() {
      return collectionForRoute({
        collection: this.$route.params.collection,
        parentIds: this.$route.params.parentIds,
      });
    },
    routeCollection() {
      return this.routeTarget.collection;
    },
    titleBook() {
      // The collection being browsed, as a card-shaped book for its Tags button.
      const { collection, pks } = this.routeTarget;
      if (collection === "root" || pks.length === 0) {
        return null;
      }
      const ids = pks.map(Number);
      return { collection, ids, pk: ids[0], childCount: 0 };
    },
    title() {
      let title;
      if (!this.$route.params.parentIds) {
        title = "All";
      } else if (this.browserTitle) {
        let names = [];
        const {
          collectionName,
          collectionNumberTo,
          collectionCount,
          collectionStartYear,
          collectionEndYear,
        } = this.browserTitle;
        const collection = this.routeCollection;
        const formattedCollectionName =
          collection === "volumes"
            ? formattedVolumeName(collectionName, collectionNumberTo)
            : collectionName;
        if (formattedCollectionName) {
          names.push(formattedCollectionName);
        }
        const years = formattedYearRange(
          collectionStartYear,
          collectionEndYear,
        );
        if (years) {
          names.push(years);
        }
        if (collectionCount) {
          const formattedCollectionCount = `of ${collectionCount}`;
          names.push(formattedCollectionCount);
        }
        title = names.join(" ");
      } else {
        title = "(Empty)";
      }
      return title;
    },
    subtitle() {
      return this.routeCollection === "folders"
        ? ""
        : this.collectionNames[this.modelCollection];
    },
  },
};
</script>

<style scoped lang="scss">
#browserToolbarTitle {
  padding-bottom: 6px;
}

/* Out of the flex flow so the title stays centred on the whole bar. */
.titleTagButton {
  position: absolute;
  top: 0px;
  right: 0px;
  height: 24px;
  display: flex;
  align-items: center;
}

.browserTitle {
  margin: 0px;
  text-align: center;
  white-space: nowrap;
  overflow-y: scroll;
}

#browserTitle {
  /* Symmetric room for the Tags button keeps a long title centred. */
  padding-inline: 24px;
  font-size: clamp(12px, 2vw, 20px);
}

#browserSubtitle {
  padding-top: 2px;
  font-size: 15px;
  color: rgb(var(--v-theme-text-disabled));
}
</style>
