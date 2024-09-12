<template>
  <v-dialog
    v-model="dialog"
    content-class="browserSearchHelp"
    fullscreen
    :scrim="false"
    transition="dialog-bottom-transition"
  >
    <template #activator="{ props }">
      <DrawerItem
        v-bind="props"
        :prepend-icon="mdiArchiveSearchOutline"
        title="Search Help"
      />
    </template>
    <div id="searchHelp">
      <CloseButton
        class="closeButton"
        title="Close Help (esc)"
        size="x-large"
        @click="dialog = false"
      />
      <SearchHelpText />
      <CloseButton
        class="closeButton"
        title="Close Help (esc)"
        size="x-large"
        @click="dialog = false"
      />
    </div>
  </v-dialog>
</template>
<script>
import { mdiArchiveSearchOutline, mdiOpenInNew } from "@mdi/js";

import SearchHelpText from "@/components/browser/search-help-text.vue";
import CloseButton from "@/components/close-button.vue";
import DrawerItem from "@/components/drawer-item.vue";
export default {
  name: "SearchHelp",
  components: { CloseButton, DrawerItem, SearchHelpText },
  data() {
    return {
      mdiOpenInNew,
      mdiArchiveSearchOutline,
      dialog: false,
    };
  },
};
</script>

<style scoped lang="scss">
#searchHelp {
  max-width: 850px;
  padding: 20px;
  padding-left: 20px;
  padding-right: 20px;
  margin: auto;
  color: rgb(var(--v-theme-textSecondary));
}
</style>
