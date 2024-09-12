<template>
  <DrawerItem :to="lastRoute" :prepend-icon="mdiBookshelf" title="Browser" />
</template>
<script>
import { mdiBookshelf } from "@mdi/js";
import { mapGetters } from "pinia";

import DrawerItem from "@/components/drawer-item.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "AdminBrowserLink",
  components: {
    DrawerItem,
  },
  data() {
    return { mdiBookshelf };
  },
  computed: {
    ...mapGetters(useBrowserStore, ["lastRoute"]),
  },
};
</script>
