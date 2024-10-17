<template>
  <CodexListItem :to="lastRoute" :prepend-icon="mdiBookshelf" title="Browser" />
</template>
<script>
import { mdiBookshelf } from "@mdi/js";
import { mapGetters } from "pinia";

import CodexListItem from "@/components/codex-list-item.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "AdminBrowserLink",
  components: {
    CodexListItem,
  },
  data() {
    return { mdiBookshelf };
  },
  computed: {
    ...mapGetters(useBrowserStore, ["lastRoute"]),
  },
};
</script>
