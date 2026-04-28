<template>
  <div>
    <v-slide-x-transition hide-on-leave>
      <v-list-item
        v-if="filterMode === 'base'"
        density="compact"
        variant="plain"
        :title="title"
        :active="isActive"
        :append-icon="filterMenuIcon"
        @click="setUIFilterMode(name)"
      />
    </v-slide-x-transition>
    <v-slide-x-reverse-transition hide-on-leave>
      <div v-if="filterMode === name">
        <header class="filterHeader">
          <v-list-item
            class="filterHeaderTitle"
            :prepend-icon="mdiChevronLeft"
            :title="lowerTitle"
            @click="setUIFilterMode('base')"
          />
          <v-list-item
            v-if="isClearable"
            density="compact"
            class="clearFilter"
            title="Clear Filter"
            :append-icon="mdiCloseCircleOutline"
            @click="onClear"
          />
          <v-text-field
            v-if="typeof choices === 'object'"
            v-model="search"
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
          @update:selected="selected"
        >
          <!--
            Manual ``v-for`` to render list items so the per-item
            slot (``#append`` for ``metronName``) can fire. The
            previous version also passed ``:items="vuetifyItems"``
            to ``v-list``; Vuetify renders the items prop directly,
            so each row was being emitted twice — once by the prop,
            once by this ``v-for``. Drop the prop to render once.
          -->
          <v-list-item
            v-for="item of vuetifyItems"
            :key="item.value"
            density="compact"
            variant="plain"
            :value="item.value"
            :title="itemTitle(item)"
            :active="item.active"
            :disabled="item.active"
            :append-icon="item.icon"
          >
            <template v-if="item.metronName" #append>
              <span class="metronName">{{ item.metronName }}</span>
            </template>
          </v-list-item>
        </v-list>
      </div>
    </v-slide-x-reverse-transition>
  </div>
</template>

<script>
import {
  mdiCheck,
  mdiChevronLeft,
  mdiChevronRight,
  mdiChevronRightCircle,
  mdiCloseCircleOutline,
} from "@mdi/js";
import { mapActions, mapState, mapWritableState } from "pinia";
import { capitalCase } from "text-case";

import { NULL_PKS, toVuetifyItems } from "@/api/v3/vuetify-items";
import { useBrowserStore } from "@/stores/browser";

const NUMERIC_FILTERS = new Set(["decade", "year"]);
const FILTER_TITLE_OVERRIDES = {
  ageRatingTagged: "Age Rating (Tagged)",
  ageRatingMetron: "Age Rating",
};

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
      mdiCloseCircleOutline,
      search: "",
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      choices(state) {
        return state.choices.dynamic[this.name];
      },
      readingDirectionTitles: (state) => state.choices.static.readingDirection,
      filter(state) {
        return state.settings.filters[this.name];
      },
    }),
    ...mapWritableState(useBrowserStore, ["filterMode"]),
    hasNone() {
      for (const item of this.choices) {
        if (
          NULL_PKS.has(item) ||
          (item instanceof Object && NULL_PKS.has(item.pk))
        ) {
          return true;
        }
      }
      return false;
    },
    isNumeric() {
      return NUMERIC_FILTERS.has(this.name);
    },
    vuetifyItems() {
      let items;
      if (this.name === "universes") {
        items = this.fixUniverseTitles(this.choices);
      } else {
        items = this.choices;
      }
      const sortBy = this.isNumeric
        ? "numeric"
        : this.name == "ageRatingMetron"
          ? ""
          : this.name == "ageRatingTagged"
            ? "metronIndex"
            : "title";
      const copyKeys =
        this.name === "ageRatingMetron"
          ? ["index"]
          : this.name === "ageRatingTagged"
            ? ["metronName", "index"]
            : [];
      const vItems = toVuetifyItems({
        items,
        filter: this.search,
        sortBy,
        copyKeys,
      });
      for (const item of vItems) {
        item.active = this.filter?.includes(item.value);
        item.icon = item.active ? mdiCheck : undefined;
        if (
          this.name === "ageRatingTagged" &&
          item.title == "None" &&
          vItems.length > 1
        ) {
          item.metronName = "Normalized To:";
        }
      }
      return vItems;
    },
    title() {
      return FILTER_TITLE_OVERRIDES[this.name] || capitalCase(this.name);
    },
    lowerTitle() {
      return this.title.toLowerCase();
    },
    isActive() {
      return this.filter && this.filter.length > 0;
    },
    filterMenuIcon() {
      return this.isActive ? mdiChevronRightCircle : mdiChevronRight;
    },
    isClearable() {
      return this.filter?.length;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "clearOneFilter",
      "fixUniverseTitles",
      "identifierSourceTitle",
      "loadAvailableFilterChoices",
      "loadFilterChoices",
    ]),
    setUIFilterMode(mode) {
      this.filterMode = mode;
      this.search = "";
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
    itemTitle(item) {
      if (this.name === "readingDirection") {
        return this.readingDirectionTitles[item.value];
      } else if (this.name === "identifierSource") {
        return this.identifierSourceTitle(item.title);
      }
      return item.title;
    },
    async _loadSubAvailableFilterChoices() {
      return this.loadAvailableFilterChoices().then(() => {
        return this.loadFilterChoices(this.name);
      });
    },
    onClear() {
      return this.clearOneFilter(this.name).then(() => {
        return this._loadSubAvailableFilterChoices();
      });
    },
  },
};
</script>

<style scoped lang="scss">
.filterHeaderTitle :deep(.v-list-item__prepend > .v-list-item__spacer) {
  display: none;
}

.filterHeaderTitle :deep(.v-list-item-title) {
  font-variant: small-caps;
  color: rbg(var(--v-theme-textDisabled));
  font-weight: bold;
  font-size: 1.6rem !important;
}

.filterGroup {
  max-height: 80vh;
  /* has to be less than the menu height */
}

.filterValuesProgress {
  margin: 10px;
  width: 88%;
}

.clearFilter {
  color: black;
  background-color: rgb(var(--v-theme-primary));
  opacity: 0.7;
}

.clearFilter:hover {
  opacity: 1;
}

.metronName {
  color: rbg(var(--v-theme-textDisabled));
  opacity: 0.7;
  text-align: right;
  font-size: smaller;
}
</style>
