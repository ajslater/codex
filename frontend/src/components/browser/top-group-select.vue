<template>
  <div>
    <v-hover v-slot="{ hover }">
      <v-select
        v-model="topGroup"
        class="toolbarSelect topGroupSelect"
        :items="topGroupChoices"
        density="compact"
        hide-details="auto"
        :label="focused || hover ? label : undefined"
        :aria-label="label"
        :menu-props="{
          maxHeight: '80vh',
          overflowY: false,
        }"
        ripple
        @focus="focused = true"
        @blur="focused = false"
      />
    </v-hover>
  </div>
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserTopGroupSelect",
  data() {
    return {
      focused: false,
      label: "top group",
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      topGroupSetting: (state) => state.settings.topGroup,
    }),
    ...mapGetters(useBrowserStore, ["topGroupChoices"]),
    topGroup: {
      get() {
        return this.topGroupSetting;
      },
      set(value) {
        if (
          (this.topGroupSetting === "f" && value !== "f") ||
          (this.topGroupSetting !== "f" && value === "f")
        ) {
          this.$router.push({ params: { group: value, pk: 0 } });
        }
        // This must happen after the push
        const settings = { topGroup: value };
        this.setSettings(settings);
      },
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
  },
};
</script>

// #topGroupSelect style is handled in browser/filter-toolbar.vue
