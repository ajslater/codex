<template>
  <!-- eslint-disable sonarjs/no-vue-bypass-sanitization -->
  <CodexListItem
    v-if="pdfInBrowserURL"
    class="readerCodexListItem"
    :prepend-icon="mdiEye"
    :append-icon="mdiOpenInNew"
    title="Read in Tab"
    :href="pdfInBrowserURL"
    target="_blank"
  />
</template>

<script>
import { mdiEye, mdiOpenInNew } from "@mdi/js";
import { mapState } from "pinia";

import { getPDFInBrowserURL } from "@/api/v3/reader";
import CodexListItem from "@/components/codex-list-item.vue";
import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderSettingsReader",
  components: { CodexListItem },
  data() {
    return {
      mdiEye,
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useReaderStore, ["isPDF"]),
    ...mapState(useReaderStore, {
      pdfInBrowserURL(state) {
        return this.isPDF && state.books?.current
          ? getPDFInBrowserURL(state.books?.current)
          : "";
      },
    }),
  },
};
</script>

<style scoped lang="scss">
// settingsSubHeader defined in settings/settings-drawer.vue
.readerCodexListItem {
  padding-left: 15px;
  padding-right: env(safe-area-inset-right);
}
</style>
