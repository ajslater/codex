<template>
  <ReaderTitleToolbar />
  <v-empty-state
    class="empty"
    headline="Book Not Found"
    title="Close the reader and find another book"
    :icon="mdiBookRemoveOutline"
  />
</template>

<script>
import { mdiBookRemoveOutline } from "@mdi/js";

import ReaderTitleToolbar from "@/components/reader/toolbars/title/reader-toolbar-title.vue";

export default {
  name: "ReaderEmpty",
  components: {
    ReaderTitleToolbar,
  },
  data() {
    return {
      mdiBookRemoveOutline,
    };
  },
};
</script>

<style scoped lang="scss">
.empty {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
