<template>
  <div id="flags" class="adminContainer">
    <div v-for="group in groupedFlags" :key="group.title" class="adminGroup">
      <div class="adminGroupHeader">
        <h3>{{ group.title }}</h3>
      </div>
      <div v-for="item in group.items" :key="`f${item.key}`" class="adminCard">
        <div class="adminCardHeader">
          <div class="adminCardInfo">
            <div class="adminCardTitle">
              {{ title(item) }}
            </div>
            <div class="adminCardDesc">
              {{ DESC[item.key] }}
            </div>
          </div>
          <div class="adminCardActions">
            <v-checkbox
              v-if="!hasValueControl(item)"
              :model-value="item.on"
              :true-value="true"
              :error-messages="errors[item.key]"
              hide-details="auto"
              @update:model-value="changeCol(item.key, 'on', $event)"
            />
          </div>
        </div>
        <!--
          Value-bearing flags (banner text, age-rating defaults,
          default browser view) render their control in the card
          body so the input/select gets the full card width without
          jamming up against the title in the header.
        -->
        <div v-if="item.key === 'BT'" class="flagValueRow">
          <v-text-field
            :model-value="banner"
            label="Banner"
            clearable
            hide-details="auto"
            density="compact"
            :error-messages="errors[item.key]"
            @update:model-value="banner = $event"
            @click:clear="banner = ''"
          />
          <v-btn
            variant="plain"
            class="flagSaveButton"
            :icon="mdiContentSaveOutline"
            title="Save Banner"
            @click="changeCol(item.key, 'value', banner)"
          />
        </div>
        <!--
          ``AA`` and ``AR`` bind to the typed FK (``ageRatingMetron``)
          on the flag row, not the legacy ``value`` string. The
          dropdown is fed directly from the live ``ageRatingMetrons``
          list loaded via the admin store — same source used on the
          Users tab — so there is no parallel static choices JSON.
        -->
        <div v-else-if="item.key === 'AR'" class="flagValueRow">
          <v-select
            :model-value="item.ageRatingMetron"
            :items="ageRatingChoices"
            item-title="name"
            item-value="pk"
            label="Age Rating Default"
            hide-details="auto"
            density="compact"
            :error-messages="errors[item.key]"
            @update:model-value="changeCol(item.key, 'ageRatingMetron', $event)"
          />
        </div>
        <div v-else-if="item.key === 'AA'" class="flagValueRow">
          <v-select
            :model-value="item.ageRatingMetron"
            :items="ageRatingChoices"
            item-title="name"
            item-value="pk"
            label="Anonymous Age Rating"
            hide-details="auto"
            density="compact"
            :error-messages="errors[item.key]"
            @update:model-value="changeCol(item.key, 'ageRatingMetron', $event)"
          />
        </div>
        <!--
          ``BG`` (Default View) reuses the existing ``TOP_GROUP``
          choices JSON so the seven labels stay in sync with the
          rest of the browser UI. Persisted on the flag's ``value``
          string column; the route-URL derivation happens server-
          side in ``admin_default_route_for``.
        -->
        <div v-else-if="item.key === 'BG'" class="flagValueRow">
          <v-select
            :model-value="item.value"
            :items="topGroupChoices"
            label="Default View"
            hide-details="auto"
            density="compact"
            :error-messages="errors[item.key]"
            @update:model-value="changeCol(item.key, 'value', $event)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mdiContentSaveOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ADMIN_FLAGS from "@/choices/admin-flag-choices.json";
import BROWSER_CHOICES from "@/choices/browser-choices.json";
import DESC from "@/components/admin/tabs/flag-descriptions.json";
import ADMIN_FLAG_GROUPS from "@/components/admin/tabs/flag-groups.json";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const VALUE_CONTROL_KEYS = new Set(["BT", "AR", "AA", "BG"]);

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
    groupedFlags() {
      /*
       * Render flags by semantic group rather than DB-insertion order.
       *
       * ``ADMIN_FLAG_GROUPS`` is the authoritative ordering — both
       * across groups and within each group's keys list. We look each
       * key up in the live ``flags`` Pinia state (skipping any not
       * yet returned by the API) and append a final "Other" group
       * for keys present on the server but missing from the JSON
       * — defensive against a server release that adds a flag
       * without a corresponding frontend update.
       */
      const flagsByKey = new Map();
      for (const item of this.flags || []) {
        flagsByKey.set(item.key, item);
      }
      const placed = new Set();
      const groups = [];
      for (const group of ADMIN_FLAG_GROUPS) {
        const items = [];
        for (const key of group.keys) {
          const item = flagsByKey.get(key);
          if (item) {
            items.push(item);
            placed.add(key);
          }
        }
        if (items.length > 0) {
          groups.push({ title: group.title, items });
        }
      }
      const orphans = [];
      for (const item of this.flags || []) {
        if (!placed.has(item.key)) {
          orphans.push(item);
        }
      }
      if (orphans.length > 0) {
        groups.push({ title: "Other", items: orphans });
      }
      return groups;
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
    hasValueControl(item) {
      /*
       * Banner-text, age-rating, and default-view flags render
       * their input or select inside the card body. Their card
       * suppresses the trailing checkbox in the header.
       */
      return VALUE_CONTROL_KEYS.has(item.key);
    },
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

.flagValueRow {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
}

.flagSaveButton {
  color: rgb(var(--v-theme-textSecondary));
  flex-shrink: 0;
}

.flagSaveButton:hover {
  color: white;
}
</style>
