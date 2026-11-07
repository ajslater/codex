<template>
  <v-combobox
    v-bind="$attrs"
    :items="items"
    :loading="loading"
    :hide-no-data="false"
    :no-data-text="noDataText"
    filtered-order="prefix"
    @update:menu="onMenu"
    @update:search="onSearch"
  >
    <template v-for="(_slot, name) in $slots" #[name]="slotData">
      <slot :name="name" v-bind="slotData || {}" />
    </template>
  </v-combobox>
</template>

<script>
/*
 * A tag editor combobox that suggests the library's existing names.
 *
 * Nothing loads until the menu opens; typing while it is open asks the
 * server again, debounced, unless a cached shorter query already holds every
 * match (see the metadata store). Free text stays allowed: a new name is
 * still typed and entered as before. Everything else -- v-model, multiple,
 * chips, label, disabled, classes, listeners and slots -- passes through.
 */
import { mapActions, mapState } from "pinia";

import { useMetadataStore } from "@/stores/metadata";

const SEARCH_DEBOUNCE_MS = 250;

export default {
  name: "TagNameCombobox",
  inheritAttrs: false,
  props: {
    // The server's field key: publisher, genres, credits, story_arcs, ...
    field: {
      type: String,
      required: true,
    },
    // Parent names that narrow the suggestions, e.g. {publisher: "DC"}.
    scope: {
      type: Object,
      default: () => ({}),
    },
    // Offered ahead of the suggestions: the opened group's own values.
    extraItems: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      menuOpen: false,
      query: "",
      searchTimer: undefined,
    };
  },
  computed: {
    ...mapState(useMetadataStore, ["tagNameChoices", "tagNamesLoading"]),
    loading() {
      return Boolean(this.tagNamesLoading[this.field]);
    },
    items() {
      const suggestions = this.tagNameChoices(
        this.field,
        this.scope,
        this.query,
      );
      // Volume names are numbers, so dedupe by their text.
      const seen = new Set();
      const items = [];
      for (const name of [...this.extraItems, ...suggestions]) {
        const key = String(name);
        if (seen.has(key)) continue;
        seen.add(key);
        items.push(name);
      }
      return items;
    },
    noDataText() {
      return this.loading ? "Loading…" : "No matches — Enter adds it";
    },
  },
  beforeUnmount() {
    clearTimeout(this.searchTimer);
  },
  methods: {
    ...mapActions(useMetadataStore, ["loadTagNames"]),
    load(q) {
      this.loadTagNames({ field: this.field, scope: this.scope, q });
    },
    onMenu(open) {
      this.menuOpen = open;
      clearTimeout(this.searchTimer);
      if (!open) return;
      // Vuetify lists every item until the user types, so ask for them all.
      this.query = "";
      this.load("");
    },
    /*
     * Vuetify also emits update:search when the model is assigned, when an
     * item is picked and after each chip is added; none of those are typing.
     * Gate on the open menu both when the timer is set and when it fires: an
     * assignment happens with the menu closed, a pick closes it before the
     * timer fires, and a chip add clears the search back to the cached "".
     */
    onSearch(value) {
      clearTimeout(this.searchTimer);
      if (!this.menuOpen) return;
      this.query = value ?? "";
      this.searchTimer = setTimeout(() => {
        if (this.menuOpen) this.load(this.query);
      }, SEARCH_DEBOUNCE_MS);
    },
  },
};
</script>
