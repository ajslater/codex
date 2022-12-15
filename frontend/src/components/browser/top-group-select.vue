<template>
  <ToolbarSelect
    v-bind="$attrs"
    v-model="topGroup"
    class="topGroupSelect"
    select-label="top group"
    :items="topGroupChoices"
    :style="style"
  />
</template>

<script>
import { mapActions, mapGetters, mapState } from "pinia";

import ToolbarSelect from "@/components/browser/toolbar-select.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserTopGroupSelect",
  components: {
    ToolbarSelect,
  },
  extends: ToolbarSelect,
  computed: {
    ...mapState(useBrowserStore, {
      topGroupSetting: (state) => state.settings.topGroup,
    }),
    ...mapGetters(useBrowserStore, [
      "topGroupChoices",
      "topGroupChoicesMaxLen",
    ]),
    topGroup: {
      get() {
        return this.topGroupSetting;
      },
      set(value) {
        if (
          (this.topGroupSetting === "f" && value !== "f") ||
          (this.topGroupSetting !== "f" && value === "f")
        ) {
          const topRoute = {
            params: { group: value, pk: 0 },
          };
          this.$router.push(topRoute);
        }
        // This must happen after the push
        const settings = { topGroup: value };
        this.setSettings(settings);
      },
    },
    style() {
      const adj = this.$vuetify.display.mobile ? -3.5 : -1;
      const len = this.topGroupChoicesMaxLen + adj + "em";
      return `width: ${len}; min-width: ${len}; max-width: ${len}`;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
  },
};
</script>

// #topGroupSelect style is handled in browser/filter-toolbar.vue
