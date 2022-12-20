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
        />
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

import { toVuetifyItems } from "@/api/v3/vuetify-items";
import {
  CHARPK_FILTERS,
  NUMERIC_FILTERS,
  useBrowserStore,
} from "@/stores/browser";

const NULL_PKS = new Set(["", -1]);

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
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      choices: function (state) {
        return state.choices.dynamic[this.name];
      },
      filter: function (state) {
        return state.settings.filters[this.name];
      },
    }),
    ...mapWritableState(useBrowserStore, ["filterMode"]),
    vuetifyItems() {
      return toVuetifyItems(
        this.choices,
        this.query,
        NUMERIC_FILTERS.includes(this.name),
        CHARPK_FILTERS.includes(this.name)
      );
    },
    title: function () {
      let title = this.name.replaceAll(/[A-Z]/g, (letter) => ` ${letter}`);
      title = title.replace("Ltr", "LTR");
      title = title[0].toUpperCase() + title.slice(1);
      return title;
    },
    lowerTitle: function () {
      return this.title.toLowerCase();
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["loadFilterChoices"]),
    setUIFilterMode(mode) {
      this.filterMode = mode;
      this.query = "";
      if (mode !== "base" && typeof this.choices !== "object") {
        this.loadFilterChoices(mode);
      }
    },
    isNullPk: (pk) => NULL_PKS.has(pk),
    selected(value) {
      const data = {
        filters: { [this.name]: value },
      };
      this.$emit("selected", data);
    },
    itemTitle(item) {
      return this.isNullPk(item.value) ? "None" : item.title;
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
</style>
