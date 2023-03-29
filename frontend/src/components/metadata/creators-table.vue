<template>
  <v-table
    v-if="sortedcreators && sortedcreators.length > 0"
    id="creatorsTable"
  >
    <template #default>
      <h2>creators</h2>
      <table class="highlight-table">
        <thead>
          <tr>
            <th class="text-left">Role</th>
            <th class="text-left">Creator</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="creator in sortedcreators" :key="creator.pk">
            <td>
              {{ roleName(creator.role.name) }}
            </td>
            <td :class="{ filteredOn: isFilteredCreator(creator.person.pk) }">
              <span class="highlight">
                {{ creator.person.name }}
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
  name: "MetadatacreatorsTable",
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
    sortedcreators: function () {
      return this.value ? [...this.value].sort(this.creatorsCompare) : [];
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
    creatorSortable: function (creator) {
      const names = creator.person.name.split(" ");
      let sortArray = [];
      if (names) {
        sortArray.push(names.slice(-1));
        if (names.length > 1) {
          sortArray.push(names.slice(0, -1));
        }
      }
      sortArray.push(creator.role.name);

      return sortArray.join(" ");
    },
    creatorsCompare: function (creatorA, creatorB) {
      const creatorSortableA = this.creatorSortable(creatorA);
      const creatorSortableB = this.creatorSortable(creatorB);
      if (creatorSortableA < creatorSortableB) return -1;
      if (creatorSortableA > creatorSortableB) return 1;
      return 0;
    },
    isFilteredCreator(pk) {
      return this.filteredCreators && this.filteredCreators.includes(pk);
    },
  },
};
</script>

<style scoped lang="scss">
#creatorsTable {
  padding: 10px;
}
#creatorsTable table {
  width: 100%;
}
#creatorsTable th,
#creatorsTable td {
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
