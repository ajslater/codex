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
    :disabled="disableCacheBook"
    label="Cache Entire Book"
    hide-details="auto"
    :true-value="true"
    :indeterminate="
      settings.cacheBook === null || settings.cacheBook === undefined
    "
    @update:model-value="$emit('update', { cacheBook: $event })"
  />

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
import { mapState } from "pinia";

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
    ...mapState(useReaderStore, ["isVertical", "isPDF", "cacheBook"]),
    ...mapState(useReaderStore, {
      choices: (state) => state.choices,
    }),
    fitToChoices() {
      return this.choicesWithoutNull("fitTo");
    },
    readingDirectionChoices() {
      return this.choicesWithoutNull("readingDirection");
    },
    disableTwoPages() {
      return this.isVertical || (this.isPDF && this.cacheBook);
    },
    disablePageTransition() {
      return this.isVertical && this.isPDF;
    },
    disableCacheBook() {
      return this.isVertical && this.isPDF;
    },
  },
  methods: {
    choicesWithoutNull(attr) {
      const choices = [];
      for (const choice of Reflect.get(this.choices, attr)) {
        if (choice.value) {
          choices.push(choice);
        }
      }
      return Object.freeze(choices);
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
