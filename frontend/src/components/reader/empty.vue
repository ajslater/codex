<template>
  <ReaderTopToolbar />
  <v-empty-state
    class="empty"
    headline="Book Not Found"
    title="Close the reader and find another book"
    :icon="mdiBookRemoveOutline"
  />
</template>

<script>
import { mdiBookRemoveOutline } from "@mdi/js";

import ReaderTopToolbar from "@/components/reader/toolbars/top/reader-toolbar-top.vue";

export default {
  name: "ReaderEmpty",
  components: {
    ReaderTopToolbar,
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
