<template>
  <v-simple-table v-if="value && value.length > 0" id="creditsTable">
    <template #default>
      <h2>Credits</h2>
      <table>
        <thead>
          <tr>
            <th class="text-left">Role</th>
            <th class="text-left">Creator</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="credit in value" :key="credit.pk">
            <td>
              {{ roleName(credit.role.name) }}
            </td>
            <td>
              {{ credit.person.name }}
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </v-simple-table>
</template>

<script>
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
  methods: {
    roleName: function (name) {
      if (name === "CoverArtist") {
        return "Cover Artist";
      }
      return name;
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
#creditsTable thead tr,
#creditsTable tr:nth-child(even) {
  background-color: #282828;
}
</style>
