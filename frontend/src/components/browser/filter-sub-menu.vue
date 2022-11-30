<template>
  <div>
    <v-slide-x-transition hide-on-leave>
      <v-list-item
        v-if="filterMode === 'base'"
        ripple
        @click="setUIFilterMode(name)"
      >
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
          <v-list-item ripple @click="setUIFilterMode('base')">
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
        <div
          v-if="typeof choices === 'object'"
          :value="filter"
          class="filterGroup overflow-y-auto"
          multiple
          @change="change"
        >
          <v-list-item
            v-for="item of vuetifyItems"
            :key="`${name}:${item.name}`"
            :value="item.pk"
            density="compact"
            ripple
          >
            <v-list-item-title v-if="isNullPk(item.pk)" class="noneItem">
              None
            </v-list-item-title>
            <v-list-item-title v-else>
              {{ item.name }}
            </v-list-item-title>
          </v-list-item>
        </div>
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
  emits: ["change"],
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
    vuetifyItems: function () {
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
    change(value) {
      const data = {
        filters: { [this.name]: value },
      };
      this.$emit("change", data);
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
  color: gray;
  font-weight: bold;
  font-size: 1.6rem !important;
}
.filterHeader {
}
.filterGroup {
  max-height: 80vh; /* has to be less than the menu height */
}
.noneItem {
  color: gray;
}
.filterValuesProgress {
  margin: 10px;
  width: 88%;
}
</style>
