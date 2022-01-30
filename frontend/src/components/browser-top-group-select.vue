<template>
  <v-hover v-slot="{ hover }">
    <v-select
      v-model="topGroup"
      class="toolbarSelect topGroupSelect"
      :items="topGroupChoices"
      dense
      hide-details="auto"
      :label="focused || hover ? label : undefined"
      :menu-props="{
        maxHeight: '80vh',
        overflowY: false,
      }"
      ripple
      @focus="focused = true"
      @blur="focused = false"
    />
  </v-hover>
</template>

<script>
import { mapGetters, mapState } from "vuex";

export default {
  name: "BrowserRootGroupSelect",
  data() {
    return {
      focused: false,
      label: "top group",
    };
  },
  computed: {
    ...mapState("browser", {
      topGroupSetting: (state) => state.settings.topGroup,
    }),
    ...mapGetters("browser", ["topGroupChoices"]),
    topGroup: {
      get() {
        return this.topGroupSetting;
      },
      set(value) {
        const settings = { topGroup: value };
        this.$store.dispatch("browser/settingChanged", settings);
      },
    },
  },
};
</script>

// #topGroupSelect style is handled in browser-filter-toolbar.vue
