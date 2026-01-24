<template>
  <ClipBoard
    class="opdsVersion"
    :title="title"
    :tooltip="TOOLTIP"
    :text="url"
    :subtitle="subtitle"
  />
</template>
<script>
import { mdiRss } from "@mdi/js";

import ClipBoard from "@/components/clipboard.vue";

const TOOLTIP = "Copy URL to clipboard";

export default {
  name: "OPDSUrl",
  props: {
    title: {
      type: String,
      required: true,
    },
    subtitle: {
      type: String,
      default: undefined,
    },
    urlPath: {
      type: String,
      required: true,
    },
  },
  components: { ClipBoard },
  data() {
    return {
      mdiRss,
      TOOLTIP,
    };
  },
  computed: {
    url() {
      return globalThis.origin + this.urlPath;
    },
  },
};
</script>
<style scoped lang="scss">
.opdsVersion {
  padding: 5px;
}
</style>
