<template>
  <v-table v-if="sortedCredits && sortedCredits.length > 0" id="creditsTable">
    <template #default>
      <h2>Credits</h2>
      <table class="highlight-table">
        <thead>
          <tr>
            <th class="text-left">Role</th>
            <th class="text-left">Creator</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="credit in sortedCredits" :key="credit.pk">
            <td>
              {{ roleName(credit.role.name) }}
            </td>
            <td :class="{ filteredOn: isFilteredCreator(credit.person.pk) }">
              <span class="highlight">
                {{ credit.person.name }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </v-table>
</template>

<script>
import { mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "MetadataCreditsTable",
  props: {
    value: {
      type: Array,
      default: undefined,
    },
  },
  data() {
    return {};
  },
  computed: {
    sortedCredits: function () {
      return this.value ? [...this.value].sort(this.creditsCompare) : [];
    },
    ...mapState(useBrowserStore, {
      filteredCreators(state) {
        return state.settings.filters.creators;
      },
    }),
  },
  methods: {
    roleName: function (name) {
      if (name === "CoverArtist") {
        return "Cover Artist";
      }
      return name;
    },
    creditSortable: function (credit) {
      const names = credit.person.name.split(" ");
      let sortArray = [];
      if (names) {
        sortArray.push(names.slice(-1));
        if (names.length > 1) {
          sortArray.push(names.slice(0, -1));
        }
      }
      sortArray.push(credit.role.name);

      return sortArray.join(" ");
    },
    creditsCompare: function (creditA, creditB) {
      const creditSortableA = this.creditSortable(creditA);
      const creditSortableB = this.creditSortable(creditB);
      if (creditSortableA < creditSortableB) return -1;
      if (creditSortableA > creditSortableB) return 1;
      return 0;
    },
    isFilteredCreator(pk) {
      return this.filteredCreators && this.filteredCreators.includes(pk);
    },
  },
};
</script>

<style scoped lang="scss">
#creditsTable {
  padding: 10px;
}
#creditsTable table {
  width: 100%;
}
#creditsTable th,
#creditsTable td {
  padding: 10px;
}
.filteredOn {
  padding-left: 0px !important;
}
.highlight {
  border-radius: 20px;
}
.filteredOn .highlight {
  padding: 10px;
  background-color: rgb(var(--v-theme-primary-darken-1));
}
</style>
