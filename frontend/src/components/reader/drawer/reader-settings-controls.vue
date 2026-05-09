<template>
  <v-radio-group
    class="displayRadioGroup"
    density="compact"
    label="Display"
    hide-details="auto"
    :model-value="settings.fitTo"
    @update:model-value="$emit('update', { fitTo: $event })"
  >
    <v-radio
      v-for="item in fitToChoices"
      :key="item.value"
      :label="item.title"
      :value="item.value"
    />
  </v-radio-group>
  <v-checkbox
    :disabled="disableTwoPages"
    class="scopedCheckbox"
    density="compact"
    label="Two pages"
    hide-details="auto"
    :model-value="settings.twoPages"
    :true-value="true"
    :indeterminate="
      settings.twoPages === null || settings.twoPages === undefined
    "
    @update:model-value="$emit('update', { twoPages: $event })"
  />
  <v-radio-group
    class="displayRadioGroup"
    density="compact"
    label="Reading Direction"
    hide-details="auto"
    :model-value="settings.readingDirection"
    @update:model-value="$emit('update', { readingDirection: $event })"
  >
    <v-radio
      v-for="item in readingDirectionChoices"
      :key="item.value"
      :label="item.title"
      :value="item.value"
    />
  </v-radio-group>
  <v-checkbox
    :model-value="settings.readRtlInReverse"
    class="scopedCheckbox"
    density="compact"
    label="Read RTL Comics LTR"
    hide-details="auto"
    :true-value="true"
    @update:model-value="$emit('update', { readRtlInReverse: $event })"
  />
  <v-checkbox
    :model-value="settings.finishOnLastPage"
    class="scopedCheckbox"
    density="compact"
    label="Finish Book On Last Page"
    hide-details="auto"
    :true-value="true"
    :indeterminate="
      settings.finishOnLastPage === null ||
      settings.finishOnLastPage === undefined
    "
    @update:model-value="$emit('update', { finishOnLastPage: $event })"
  />
  <v-checkbox
    v-tooltip="{
      openDelay,
      text: 'Animate page turns when reading horizontally.',
    }"
    :model-value="settings.pageTransition"
    class="scopedCheckbox"
    density="compact"
    :disabled="disablePageTransition"
    label="Animate Page Turns"
    hide-details="auto"
    :true-value="true"
    :indeterminate="
      settings.pageTransition === null || settings.pageTransition === undefined
    "
    @update:model-value="$emit('update', { pageTransition: $event })"
  />
  <v-checkbox
    v-tooltip="{
      openDelay,
      text: 'Cache all pages from this book in the browser',
    }"
    :model-value="settings.cacheBook"
    class="scopedCheckbox"
    density="compact"
    label="Cache Entire Book"
    hide-details="auto"
    :true-value="true"
    :indeterminate="
      settings.cacheBook === null || settings.cacheBook === undefined
    "
    @update:model-value="$emit('update', { cacheBook: $event })"
  />
  <v-radio-group
    v-if="isPDF"
    v-tooltip="{
      openDelay,
      text:
        'Auto: server decides per page. Image: always rasterize. ' +
        'Vector: always render through pdf.js.',
    }"
    class="displayRadioGroup"
    density="compact"
    label="PDF Rendering"
    hide-details="auto"
    :model-value="pdfRenderMode"
    @update:model-value="setPdfRenderMode"
  >
    <v-radio label="Automatic" value="auto" />
    <v-radio label="Force image" value="image" />
    <v-radio label="Force vector" value="pdf" />
  </v-radio-group>

  <v-btn
    v-if="showClear"
    id="clearSettingsButton"
    v-tooltip="{
      openDelay,
      text: 'Use the default settings for all comics for this comic',
    }"
    :disabled="clearDisabled"
    @click="$emit('clear')"
  >
    Clear Settings
  </v-btn>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useReaderStore } from "@/stores/reader";

export default {
  name: "ReaderSettingsControls",
  props: {
    settings: {
      type: Object,
      required: true,
    },
    showClear: {
      type: Boolean,
      default: false,
    },
    clearDisabled: {
      type: Boolean,
      default: true,
    },
  },
  emits: ["update", "clear"],
  data() {
    return {
      openDelay: 2000,
    };
  },
  computed: {
    ...mapState(useReaderStore, ["isVertical", "isPDF"]),
    ...mapState(useReaderStore, {
      choices: (state) => state.choices,
      pdfRenderMode: (state) => state.clientSettings?.pdfRenderMode || "auto",
    }),
    fitToChoices() {
      return this.choicesWithoutNull("fitTo");
    },
    readingDirectionChoices() {
      return this.choicesWithoutNull("readingDirection");
    },
    disableTwoPages() {
      /*
       * Two-page rendering is meaningful in horizontal mode only.
       * PDFs handle two-page correctly through both ``<img>`` and
       * ``<PDFDoc>`` paths now, so the old PDF carve-out is gone.
       */
      return this.isVertical;
    },
    disablePageTransition() {
      // Page-turn animations only make sense in horizontal mode.
      return this.isVertical;
    },
  },
  methods: {
    ...mapActions(useReaderStore, ["setSettingsClient"]),
    choicesWithoutNull(attr) {
      const choices = [];
      for (const choice of Reflect.get(this.choices, attr)) {
        if (choice.value) {
          choices.push(choice);
        }
      }
      return Object.freeze(choices);
    },
    setPdfRenderMode(value) {
      this.setSettingsClient({ pdfRenderMode: value });
    },
  },
};
</script>

<style scoped lang="scss">
.scopedCheckbox {
  padding-left: 6px;
}

#clearSettingsButton {
  margin-top: 6px;
  margin-bottom: 4px;
}
</style>
