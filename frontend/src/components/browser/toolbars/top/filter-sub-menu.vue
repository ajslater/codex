<template>
  <div>
    <v-slide-x-transition hide-on-leave>
      <v-list-item v-if="filterMode === 'base'" @click="setUIFilterMode(name)">
        <v-list-item-title class="filterMenu">
          {{ title }}
          <v-icon v-if="filter && filter.length > 0" class="nameChevron">
            {{ mdiChevronRightCircle }}
          </v-icon>
          <v-icon v-else class="nameChevron">
            {{ mdiChevronRight }}
          </v-icon>
        </v-list-item-title>
      </v-list-item>
    </v-slide-x-transition>
    <v-slide-x-reverse-transition hide-on-leave>
      <div v-if="filterMode === name">
        <header class="filterHeader">
          <v-list-item @click="setUIFilterMode('base')">
            <v-list-item-title class="filterTitle">
              <v-icon>{{ mdiChevronLeft }}</v-icon
              >{{ lowerTitle }}
            </v-list-item-title>
          </v-list-item>
          <v-text-field
            v-if="typeof choices === 'object'"
            v-model="query"
            placeholder="Filter"
            full-width
            density="compact"
            filled
            rounded
            hide-details="auto"
            @focus="filterMode = name"
          />
          <v-progress-linear
            v-else
            class="filterValuesProgress"
            rounded
            indeterminate
          />
        </header>
        <v-list
          v-if="typeof choices === 'object'"
          :model-value="filter"
          class="filterGroup overflow-y-auto"
          density="compact"
          multiple
          :items="vuetifyItems"
          @update:selected="selected"
        >
          <v-list-item
            v-if="hasNone"
            :key="-1"
            title="None"
            :value="-1"
            class="noneItem"
          />
          <v-list-item
            v-for="item of vuetifyItems"
            :key="item.value"
            :title="itemTitle(item)"
            :value="item.value"
            :class="{ noneItem: +item.value == nullCode }"
          />
        </v-list>
      </div>
    </v-slide-x-reverse-transition>
  </div>
</template>

<script>
import {
  mdiChevronLeft,
  mdiChevronRight,
  mdiChevronRightCircle,
} from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";

import { NULL_PKS, toVuetifyItems } from "@/api/v3/vuetify-items";
import CHOICES from "@/choices";
import { useBrowserStore } from "@/stores/browser";
import { camelToTitleCase } from "@/to-case";

const VUETIFY_NULL_CODE = CHOICES.browser.vuetifyNullCode;

export default {
  name: "BrowserFilterSubMenu",
  props: {
    name: {
      type: String,
      required: true,
    },
  },
  emits: ["selected"],
  data() {
    return {
      mdiChevronLeft,
      mdiChevronRight,
      mdiChevronRightCircle,
      query: "",
      nullCode: VUETIFY_NULL_CODE,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      choices(state) {
        return state.choices.dynamic[this.name];
      },
      readingDirectionTitles: (state) => state.choices.static.readingDirection,
      identifierTypeTitles: (state) => state.choices.static.identifierType,
      filter(state) {
        return state.settings.filters[this.name];
      },
    }),
    ...mapWritableState(useBrowserStore, ["filterMode"]),
    hasNone() {
      for (const item of this.choices) {
        if (NULL_PKS.has(item.pk)) {
          return true;
        }
      }
      return false;
    },
    vuetifyItems() {
      return toVuetifyItems(this.choices, this.query);
    },
    title: function () {
      return camelToTitleCase(this.name);
    },
    lowerTitle: function () {
      return this.title.toLowerCase();
    },
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "identifierTypeTitle",
      "loadFilterChoices",
    ]),
    setUIFilterMode(mode) {
      this.filterMode = mode;
      this.query = "";
      if (mode !== "base" && typeof this.choices !== "object") {
        this.loadFilterChoices(mode);
      }
    },
    selected(value) {
      const data = {
        filters: { [this.name]: value },
      };
      this.$emit("selected", data);
    },
    itemTitle: function (item) {
      if (this.name === "readingDirection") {
        return this.readingDirectionTitles[item.value];
      } else if (this.name === "identifierType") {
        return this.identifierTypeTitle(item.title);
      }
      return item.title;
    },
  },
};
</script>

<style scoped lang="scss">
.filterMenu {
  line-height: 24px !important;
}
.nameChevron {
  float: right;
}
.filterTitle {
  font-variant: small-caps;
  color: rbg(var(--v-theme-textDisabled));
  font-weight: bold;
  font-size: 1.6rem !important;
}
.filterHeader {
}
.filterGroup {
  max-height: 80vh; /* has to be less than the menu height */
}
:deep(.noneItem .v-item-title) {
  color: rbg(var(--v-theme-textDisabled)) !important;
}
.filterValuesProgress {
  margin: 10px;
  width: 88%;
}
.noneItem {
  opacity: 0.5;
}
</style>
