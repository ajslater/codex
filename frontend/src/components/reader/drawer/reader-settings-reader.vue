<template>
  <div class="settingsSubHeader">Reader Settings</div>
  <v-checkbox
    class="readerCodexListItem"
    :model-value="finishOnLastPage"
    density="compact"
    label="Finish Book On Last Page"
    hide-details="auto"
    :true-value="true"
    @update:model-value="setSettingsGlobal({ finishOnLastPage: $event })"
  />
  <v-checkbox
    v-tooltip="{
      openDelay,
      text: 'Animate page turns when reading horizontally.',
    }"
    :model-value="pageTransition"
    class="readerCodexListItem"
    density="compact"
    :disabled="disablePageTransition"
    label="Animate Page Turns"
    hide-details="auto"
    :true-value="true"
    @update:model-value="setSettingsGlobal({ pageTransition: $event })"
  />
  <v-checkbox
    v-tooltip="{
      openDelay,
      text: 'Cache all pages from this book in the browser',
    }"
    :model-value="cacheBook"
    class="readerCodexListItem"
    density="compact"
    :disabled="disableCacheBook"
    label="Cache Entire Book"
    hide-details="auto"
    :true-value="true"
    @update:model-value="setSettingsClient({ cacheBook: $event })"
  />

  <!-- eslint-disable sonarjs/no-vue-bypass-sanitization -->
  <CodexListItem
    v-if="pdfInBrowserURL"
    :prepend-icon="mdiEye"
    :append-icon="mdiOpenInNew"
    title="Read in Tab"
    :href="pdfInBrowserURL"
    target="_blank"
  />
</template>

<script>
import { mdiEye, mdiOpenInNew } from "@mdi/js";
import { mapActions, mapState } from "pinia";

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
      openDelay: 2000,
    };
  },
  computed: {
    ...mapState(useReaderStore, ["isVertical", "isPDF", "cacheBook"]),
    ...mapState(useReaderStore, {
      pdfInBrowserURL(state) {
        return this.isPDF && state.books?.current
          ? getPDFInBrowserURL(state.books?.current)
          : "";
      },
      finishOnLastPage: (state) => state.readerSettings.finishOnLastPage,
      pageTransition: (state) => state.readerSettings.pageTransition,
    }),
    disableCacheBook() {
      return this.isVertical && this.isPDF;
    },
    disablePageTransition() {
      return this.isVertical && this.isPDF;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["setSettingsGlobal", "setSettingsClient"]),
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
