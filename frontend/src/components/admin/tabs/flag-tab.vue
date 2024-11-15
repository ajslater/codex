<template>
  <v-table class="highlight-table flags-table" :items="flags" fixed-header>
    <thead>
      <tr>
        <th>Description</th>
        <th>Value</th>
        <th>Enabled</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="item in flags" :key="`f${item.key}`">
        <td class="nameCol" :colspan="colspan(item)">
          <h4>{{ title(item) }}</h4>
          <p class="desc">
            {{ DESC[item.key] }}
          </p>
        </td>
        <td v-if="item.key === 'BT'" class="bannerTextField">
          <v-text-field
            :model-value="banner"
            label="Banner"
            clearable
            hide-details="auto"
            :error-messages="errors[item.key]"
            @update:model-value="banner = $event"
            @click:clear="banner = ''"
          />
        </td>
        <td>
          <v-btn
            v-if="item.key === 'BT'"
            variant="plain"
            class="flagSaveButton"
            :icon="mdiContentSaveOutline"
            title="Save Banner"
            @click="changeCol(item.key, 'value', banner)"
          />
          <v-checkbox
            v-else
            :model-value="item.on"
            :true-value="true"
            :error-messages="errors[item.key]"
            hide-details="auto"
            @update:model-value="changeCol(item.key, 'on', $event)"
          />
        </td>
      </tr>
    </tbody>
  </v-table>
</template>

<script>
import { mdiContentSaveOutline } from "@mdi/js";
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
      DESC,
      banner: "",
      mdiContentSaveOutline,
      lastUpdate: {
        name: "",
        field: undefined,
      },
      errors: {},
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
    }),
    ...mapState(useAdminStore, {
      flags: (state) => state.flags,
    }),
    storeBanner() {
      for (const item of this.flags) {
        if (item.key === "BT") {
          return item.value;
        }
      }
      return "";
    },
  },
  watch: {
    storeBanner(to) {
      this.banner = to;
    },
  },
  mounted() {
    this.loadTables(["Flag"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow", "clearErrors", "loadTables"]),
    setError(name, field) {
      if (this.formErrors && this.formErrors.length > 0) {
        this.errors[name] = this.formErrors[0][field];
      } else {
        delete this.errors[name];
      }
    },
    changeCol(name, field, val) {
      this.lastUpdate.name = name;
      this.lastUpdate.field = field;
      const data = { [field]: val };
      this.updateRow("Flag", name, data)
        .then(() => {
          return this.setError(name, field);
        })
        .catch(console.error);
    },
    title(item) {
      return ADMIN_FLAGS[item.key];
    },
    colspan(item) {
      return item.key === "BT" ? 1 : 2;
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

.bannerTextField {
  min-width: 16em;
}

.flagSaveButton {
  color: rgb(var(--v-theme-textSecondary));
  padding-right: 12px;
}

.flagSaveButton:hover {
  color: white;
}
</style>
