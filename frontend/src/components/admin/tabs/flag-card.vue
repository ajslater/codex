<template>
  <div v-if="item" class="adminCard">
    <div class="adminCardHeader">
      <div class="adminCardInfo">
        <div class="adminCardTitle">
          {{ title }}
        </div>
        <div class="adminCardDesc">
          {{ DESC[itemKey] }}
        </div>
      </div>
      <div class="adminCardActions">
        <v-checkbox
          v-if="!hasValueControl"
          :model-value="item.on"
          :true-value="true"
          :error-messages="error"
          hide-details="auto"
          @update:model-value="changeCol('on', $event)"
        />
      </div>
    </div>
    <!--
      Value-bearing flags (banner text, age-rating defaults,
      default browser view, page size) render their control in
      the card body so the input/select gets the full card width
      without jamming up against the title in the header.
    -->
    <div v-if="itemKey === 'BT'" class="flagValueRow">
      <v-text-field
        :model-value="banner"
        label="Banner"
        clearable
        hide-details="auto"
        density="compact"
        :error-messages="error"
        @update:model-value="banner = $event"
        @click:clear="banner = ''"
      />
      <v-btn
        variant="plain"
        class="flagSaveButton"
        :icon="mdiContentSaveOutline"
        title="Save Banner"
        @click="changeCol('value', banner)"
      />
    </div>
    <!--
      ``AA`` and ``AR`` bind to the typed FK (``ageRatingMetron``)
      on the flag row, not the legacy ``value`` string. The
      dropdown is fed directly from the live ``ageRatingMetrons``
      list loaded via the admin store.
    -->
    <div v-else-if="itemKey === 'AR'" class="flagValueRow">
      <v-select
        :model-value="item.ageRatingMetron"
        :items="ageRatingChoices"
        item-title="name"
        item-value="pk"
        label="Age Rating Default"
        hide-details="auto"
        density="compact"
        :error-messages="error"
        @update:model-value="changeCol('ageRatingMetron', $event)"
      />
    </div>
    <div v-else-if="itemKey === 'AA'" class="flagValueRow">
      <v-select
        :model-value="item.ageRatingMetron"
        :items="ageRatingChoices"
        item-title="name"
        item-value="pk"
        label="Anonymous Age Rating"
        hide-details="auto"
        density="compact"
        :error-messages="error"
        @update:model-value="changeCol('ageRatingMetron', $event)"
      />
    </div>
    <!--
      ``BG`` (Default View) reuses the existing ``TOP_COLLECTION``
      choices JSON so the seven labels stay in sync with the
      rest of the browser UI. Persisted on the flag's ``value``
      string column; the route-URL derivation happens server-
      side in ``admin_default_route_for``.
    -->
    <div v-else-if="itemKey === 'BG'" class="flagValueRow">
      <v-select
        :model-value="item.value"
        :items="topCollectionChoices"
        label="Default View"
        hide-details="auto"
        density="compact"
        :error-messages="error"
        @update:model-value="changeCol('value', $event)"
      />
    </div>
    <!--
      ``MP`` (Browser Page Size) is an int stored in the ``value``
      column. The ``CM`` custom-cover upload cap uses the same
      backing flag but its control lives on the Custom Covers tab.
    -->
    <div v-else-if="itemKey === 'MP'" class="flagValueRow">
      <v-text-field
        :model-value="item.value"
        type="number"
        :min="pageSizeRange[0]"
        :max="pageSizeRange[1]"
        :rules="pageSizeRules"
        label="Items per page"
        hide-details="auto"
        density="compact"
        :error-messages="error"
        @update:model-value="changeCol('value', $event, pageSizeRange)"
      />
    </div>
  </div>
</template>

<script>
import { mdiContentSaveOutline } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ADMIN_FLAGS from "@/choices/admin-flag-choices.json";
import BROWSER_CHOICES from "@/choices/browser-choices.json";
import LIMITS from "@/choices/limits.json";
import DESC from "@/components/admin/tabs/flag-descriptions.json";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const VALUE_CONTROL_KEYS = new Set(["BT", "AR", "AA", "BG", "MP"]);

export default {
  name: "AdminFlagCard",
  props: {
    itemKey: { type: String, required: true },
  },
  data() {
    return {
      DESC,
      banner: "",
      mdiContentSaveOutline,
      lastUpdate: {
        field: undefined,
      },
      error: undefined,
      // Static, so they belong in data rather than computed.
      pageSizeRange: LIMITS.browserMaxObjPerPage,
      pageSizeRules: Object.freeze([
        [
          "$intRange",
          LIMITS.browserMaxObjPerPage,
          "Must be between {0} and {1}",
        ],
      ]),
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      formFieldErrors: (state) => state.form.fieldErrors,
    }),
    ...mapState(useAdminStore, {
      flags: (state) => state.flags,
      ageRatingMetrons: (state) => state.ageRatingMetrons,
    }),
    item() {
      return (this.flags || []).find((f) => f.key === this.itemKey);
    },
    title() {
      return ADMIN_FLAGS[this.itemKey];
    },
    hasValueControl() {
      return VALUE_CONTROL_KEYS.has(this.itemKey);
    },
    storeBanner() {
      return this.item?.value ?? "";
    },
    ageRatingChoices() {
      return this.ageRatingMetrons || [];
    },
    topCollectionChoices() {
      return BROWSER_CHOICES.TOP_COLLECTION || [];
    },
  },
  watch: {
    storeBanner: {
      immediate: true,
      handler(to) {
        if (this.itemKey === "BT") {
          this.banner = to;
        }
      },
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["updateRow"]),
    setError(field) {
      // ``formErrors[0]`` was a message string, never a field map, so
      // ``Reflect.get(..., field)`` was always undefined and a flag
      // error could never render. The normalized map is keyed by field.
      this.error = this.formFieldErrors?.[field];
    },
    changeCol(field, val, range) {
      // This control has no v-form and PATCHes on every keystroke, so
      // rules alone display a message without stopping the write. A
      // saved 0 here is a live 500 -- ``ceil(count / 0)`` -- so the
      // write itself has to be gated.
      if (range && !this.inRange(val, range)) {
        const [low, high] = range;
        this.error = `Must be between ${low} and ${high}`;
        return;
      }
      this.lastUpdate.field = field;
      const data = { [field]: val };
      this.updateRow("Flag", this.itemKey, data)
        .then(() => {
          return this.setError(field);
        })
        .catch(console.error);
    },
    inRange(val, [low, high]) {
      const num = Number(val);
      return Number.isInteger(num) && num >= low && num <= high;
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
  color: rgb(var(--v-theme-text-secondary));
  flex-shrink: 0;
}

.flagSaveButton:hover {
  color: white;
}
</style>
