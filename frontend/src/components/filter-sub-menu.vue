<template>
  <div>
    <v-slide-x-transition hide-on-leave>
      <v-list-item v-if="filterMode === 'base'" @click="setFilterMode(name)">
        <v-list-item-content>
          <v-list-item-title class="filterMenu">
            {{ title }}
            <v-icon v-if="filter && filter.length > 0" class="nameChevron">{{
              mdiChevronRightCircle
            }}</v-icon>
            <v-icon v-else class="nameChevron">{{ mdiChevronRight }}</v-icon>
          </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </v-slide-x-transition>
    <v-slide-x-reverse-transition hide-on-leave>
      <div v-if="filterMode === name">
        <header class="filterHeader">
          <v-list-item @click="setFilterMode('base')">
            <v-list-item-content>
              <v-list-item-title class="filterTitle"
                ><v-icon>{{ mdiChevronLeft }}</v-icon
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
              <v-list-item-title>{{ item.name }}</v-list-item-title>
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
import { mapState } from "vuex";

import { toVuetifyItems } from "@/api/v2/list-items";

export default {
  name: "FilterSubMenu",
  props: {
    name: {
      type: String,
      required: true,
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
    ...mapState("browser", {
      formChoices: function (state) {
        return state.formChoices[this.name];
      },
      filterSetting: function (state) {
        return state.settings.filters[this.name];
      },
      filterMode: (state) => state.filterMode,
    }),
    vuetifyItems: function () {
      return toVuetifyItems(undefined, this.formChoices, this.query);
    },
    filter: {
      get() {
        return this.filterSetting;
      },
      set(value) {
        const data = {
          filters: { [this.name]: value },
        };
        this.$store.dispatch("browser/settingChanged", data);
        this.$emit("sub-menu-click");
      },
    },
    title: function () {
      const words = this.name.split("_");
      let title = "";
      for (const index in words) {
        if (Object.prototype.hasOwnProperty.call(words, index)) {
          // Capitalize words
          const word = words[index];
          const capWord =
            word === "ltr"
              ? "LTR"
              : word.charAt(0).toUpperCase() + word.slice(1);
          // Append to title
          if (index) {
            title += " ";
          }
          title += capWord;
        }
      }
      return title;
    },
    lowerTitle: function () {
      return this.name.replace("_", " ");
    },
  },
  methods: {
    setFilterMode(mode) {
      this.$store.dispatch("browser/filterModeChanged", {
        group: this.$route.params.group,
        pk: this.$route.params.pk,
        mode,
      });
      this.query = "";
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
</style>
