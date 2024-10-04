<template>
  <v-table class="highlight-table flags-table" :items="flags" fixed-header>
    <thead>
      <tr>
        <th>Description</th>
        <th>Enabled</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="item in flags" :key="`f${item.key}`">
        <td class="nameCol">
          <h4>{{ title(item) }}</h4>
          <p class="desc">
            {{ DESC[item.key] }}
          </p>
        </td>
        <td>
          <v-checkbox
            :model-value="item.on"
            :true-value="true"
            :error-messages="getFormErrors(item.key, 'on')"
            hide-details="auto"
            @update:model-value="changeCol(item.key, 'on', $event)"
          />
        </td>
      </tr>
    </tbody>
  </v-table>
</template>

<script>
import { mapActions, mapState } from "pinia";

import ADMIN_FLAGS from "@/choices/admin-flag-choices.json";
import DESC from "@/components/admin/tabs/flag-descriptions.json";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

export default {
  name: "AdminFlagsTab",
  components: {},
  data() {
    return {
      lastUpdate: {
        name: "",
        field: undefined,
      },
      DESC,
    };
  },
  computed: {
    ...mapState(useCommonStore, ["formErrors"]),
    ...mapState(useAdminStore, ["flags"]),
  },
  mounted() {
    this.loadTables(["Flag"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow", "clearErrors", "loadTables"]),
    changeCol(name, field, val) {
      this.lastUpdate.name = name;
      this.lastUpdate.field = field;
      const data = { [field]: val };
      this.updateRow("Flag", name, data);
    },
    getFormErrors(name, field) {
      if (name === this.lastUpdate.name && field === this.lastUpdate.field) {
        return this.formErrors;
      }
    },
    title(item) {
      return ADMIN_FLAGS[item.key];
    },
  },
};
</script>

<style scoped lang="scss">
.flags-table {
  max-width: 100vw !important;
  margin-bottom: 24px;
}

.nameCol {
  padding-top: 0.5em !important;
}

.desc {
  margin-top: 1em;
  margin-bottom: 0.5em;
  color: rgb(var(--v-theme-textSecondary));
}
</style>
