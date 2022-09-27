<template>
  <div>
    <v-slide-x-transition hide-on-leave>
      <v-list-item
        v-if="filterMode === 'base'"
        ripple
        @click="setUIFilterMode(name)"
      >
        <v-list-item-content>
          <v-list-item-title class="filterMenu">
            {{ title }}
            <v-icon v-if="filter && filter.length > 0" class="nameChevron">
              {{ mdiChevronRightCircle }}
            </v-icon>
            <v-icon v-else class="nameChevron">
              {{ mdiChevronRight }}
            </v-icon>
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-slide-x-transition>
    <v-slide-x-reverse-transition hide-on-leave>
      <div v-if="filterMode === name">
        <header class="filterHeader">
          <v-list-item ripple @click="setUIFilterMode('base')">
            <v-list-item-content>
              <v-list-item-title class="filterTitle">
                <v-icon>{{ mdiChevronLeft }}</v-icon
                >{{ lowerTitle }}
              </v-list-item-title>
            </v-list-item-content>
          </v-list-item>
          <v-text-field
            v-model="query"
            placeholder="Filter"
            full-width
            dense
            filled
            rounded
            hide-details="auto"
            @focus="filterMode = name"
          />
        </header>
        <v-list-item-group
          v-model="filter"
          class="filterGroup overflow-y-auto"
          multiple
        >
          <v-list-item
            v-for="item of vuetifyItems"
            :key="`${name}:${item.name}`"
            :value="item.pk"
            dense
            ripple
          >
            <v-list-item-content>
              <v-list-item-title v-if="isNullPk(item.pk)" class="noneItem">
                None
              </v-list-item-title>
              <v-list-item-title v-else>
                {{ item.name }}
              </v-list-item-title>
            </v-list-item-content>
          </v-list-item>
        </v-list-item-group>
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
import { useBrowserStore } from "@/stores/browser";

const NULL_PKS = new Set(["", -1]);

export default {
  name: "BrowserFilterSubMenu",
  props: {
    name: {
      type: String,
      required: true,
    },
    isNumeric: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["sub-menu-click"],
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
      filterSetting: function (state) {
        return state.settings.filters[this.name];
      },
    }),
    ...mapWritableState(useBrowserStore, ["filterMode"]),
    vuetifyItems: function () {
      return toVuetifyItems(this.choices, this.query, this.isNumeric);
    },
    filter: {
      get() {
        return this.filterSetting;
      },
      set(value) {
        const data = {
          filters: { [this.name]: value },
        };
        this.setSettings(data);
        this.$emit("sub-menu-click");
      },
    },
    title: function () {
      let title = this.name.replace(/[A-Z]/g, (letter) => ` ${letter}`);
      title = title.replace("Ltr", "LTR");
      title = title[0].toUpperCase() + title.slice(1);
      return title;
    },
    lowerTitle: function () {
      return this.title.toLowerCase();
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    setUIFilterMode(mode) {
      this.filterMode = mode;
      this.query = "";
    },
    isNullPk: (pk) => NULL_PKS.has(pk),
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
</style>
