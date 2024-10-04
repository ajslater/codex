<template>
  <v-dialog
    v-model="isSearchHelpOpen"
    content-class="browserSearchHelp"
    fullscreen
    :scrim="false"
    transition="dialog-bottom-transition"
  >
    <template #activator="{ props }">
      <v-btn
        v-bind="props"
        :icon="mdiLifebuoy"
        title="Search Help"
        :density="buttonDensity"
      />
    </template>
    <div id="searchHelp">
      <SearchHelpText />
    </div>
  </v-dialog>
</template>
<script>
import { mdiLifebuoy, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import SearchHelpText from "@/components/browser/toolbars/search/search-help-text.vue";
import { useBrowserStore } from "@/stores/browser";
export default {
  name: "SearchHelp",
  components: { SearchHelpText },
  data() {
    return {
      mdiOpenInNew,
      mdiLifebuoy,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      isSearchHelpOpenState: (state) => state.isSearchHelpOpen,
    }),
    isSearchHelpOpen: {
      get() {
        return this.isSearchHelpOpenState;
      },
      set(value) {
        this.setSearchHelpOpen(value);
      },
    },
    buttonDensity() {
      return this.$vuetify.display.smAndDown ? "compact" : "comfortable";
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSearchHelpOpen"]),
  },
};
</script>

<style scoped lang="scss">
$topMargin: calc(96px + 12px);

:deep(.browserSearchHelp) {
  top: $topMargin;
  overflow-y: auto !important;
  opacity: 0.9;
}

#searchHelp {
  padding: 20px;
  margin: auto;
  margin-bottom: $topMargin;
}
</style>
