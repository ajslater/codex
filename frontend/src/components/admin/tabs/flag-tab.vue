<template>
  <v-table id="flags-table" :items="flags" striped="odd">
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
          <div class="text-title-small title">{{ title(item) }}</div>
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
        <!--
          ``AA`` and ``AR`` bind to the typed FK (``ageRatingMetron``)
          on the flag row, not the legacy ``value`` string. The
          dropdown is fed directly from the live ``ageRatingMetrons``
          list loaded via the admin store — same source used on the
          Users tab — so there is no parallel static choices JSON.
        -->
        <td v-else-if="item.key === 'AR'" class="ageRatingField">
          <v-select
            :model-value="item.ageRatingMetron"
            :items="ageRatingChoices"
            item-title="name"
            item-value="pk"
            label="Age Rating Default"
            hide-details="auto"
            :error-messages="errors[item.key]"
            @update:model-value="changeCol(item.key, 'ageRatingMetron', $event)"
          />
        </td>
        <td v-else-if="item.key === 'AA'" class="ageRatingField">
          <v-select
            :model-value="item.ageRatingMetron"
            :items="ageRatingChoices"
            item-title="name"
            item-value="pk"
            label="Anonymous Age Rating"
            hide-details="auto"
            :error-messages="errors[item.key]"
            @update:model-value="changeCol(item.key, 'ageRatingMetron', $event)"
          />
        </td>
        <!--
          ``BG`` (Default View) reuses the existing ``TOP_GROUP``
          choices JSON so the seven labels stay in sync with the
          rest of the browser UI. Persisted on the flag's ``value``
          string column; the route-URL derivation happens server-
          side in ``admin_default_route_for``.
        -->
        <td v-else-if="item.key === 'BG'" class="topGroupField">
          <v-select
            :model-value="item.value"
            :items="topGroupChoices"
            label="Default View"
            hide-details="auto"
            :error-messages="errors[item.key]"
            @update:model-value="changeCol(item.key, 'value', $event)"
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
          <template
            v-else-if="
              item.key === 'AR' || item.key === 'AA' || item.key === 'BG'
            "
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
import BROWSER_CHOICES from "@/choices/browser-choices.json";
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
      ageRatingMetrons: (state) => state.ageRatingMetrons,
    }),
    storeBanner() {
      for (const item of this.flags) {
        if (item.key === "BT") {
          return item.value;
        }
      }
      return "";
    },
    ageRatingChoices() {
      /*
       * ``AgeRatingMetron`` rows ordered by index (Everyone..Adult) via
       * the model's default ordering; ``Unknown`` is filtered out server
       * side — safe to consume as-is.
       */
      return this.ageRatingMetrons || [];
    },
    topGroupChoices() {
      /*
       * Reuse the existing ``TOP_GROUP`` choices JSON so the labels
       * stay in sync with the rest of the browser UI. The 7 entries
       * (Folders / Story Arcs / Publishers / Imprints / Series /
       * Volumes / Issues) are the legitimate values for the BG flag;
       * the route-URL derivation runs server-side.
       */
      return BROWSER_CHOICES.TOP_GROUP || [];
    },
  },
  watch: {
    storeBanner(to) {
      this.banner = to;
    },
  },
  mounted() {
    // ``AgeRatingMetron`` feeds the AA/AR dropdowns.
    this.loadTables(["Flag", "AgeRatingMetron"]);
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow", "clearErrors", "loadTables"]),
    setError(name, field) {
      if (this.formErrors && this.formErrors.length > 0) {
        Reflect.set(this.errors, name, Reflect.get(this.formErrors[0], field));
      } else {
        Reflect.deleteProperty(this.errors, name);
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
      return ["BT", "AR", "AA", "BG"].includes(item.key) ? 1 : 2;
    },
  },
};
</script>

<style scoped lang="scss">
#flags-table {
  max-width: 100vw !important;
  margin-bottom: 24px;
  background-color: inherit;
}

.nameCol {
  padding-top: 1em !important;
}

.title {
  font-weight: bolder;
}

.desc {
  margin-top: 1em;
  margin-bottom: 0.5em;
  color: rgb(var(--v-theme-textSecondary));
}

.bannerTextField {
  min-width: 16em;
}

.ageRatingField {
  min-width: 12em;
}

.topGroupField {
  min-width: 12em;
}

.flagSaveButton {
  color: rgb(var(--v-theme-textSecondary));
  padding-right: 12px;
}

.flagSaveButton:hover {
  color: white;
}
</style>
