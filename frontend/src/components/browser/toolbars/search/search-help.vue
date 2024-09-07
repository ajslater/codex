<template>
  <v-dialog
    v-model="dialog"
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

import SearchHelpText from "@/components/browser/toolbars/search/search-help-text.vue";
export default {
  name: "SearchHelp",
  components: { SearchHelpText },
  data() {
    return {
      mdiOpenInNew,
      mdiLifebuoy,
      dialog: false,
    };
  },
  computed: {
    buttonDensity() {
      return this.$vuetify.display.smAndDown ? "compact" : "comfortable";
    },
  },
};
</script>

<style scoped lang="scss">
$topMargin: calc(96px + 12px);

:deep(.browserSearchHelp) {
  top: $topMargin;
  opacity: 0.9;
}

#searchHelp {
  padding: 20px;
  margin: auto;
  margin-bottom: $topMargin;
  overflow-y: auto !important;
}
</style>
