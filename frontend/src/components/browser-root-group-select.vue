<template>
  <v-select
    v-model="rootGroup"
    :items="rootGroupChoices"
    class="toolbarSelect rootGroupSelect"
    :label="label"
    dense
    hide-details="auto"
    ripple
    @focus="label = 'group by'"
    @blur="label = ''"
  />
</template>

<script>
import { mapGetters, mapState } from "vuex";
export default {
  name: "BrowserRootGroupSelect",
  data() {
    return {
      label: "",
    };
  },
  computed: {
    ...mapState("browser", {
      rootGroupSetting: (state) => state.settings.rootGroup,
    }),
    ...mapGetters("browser", ["rootGroupChoices"]),
    rootGroup: {
      get() {
        return this.rootGroupSetting;
      },
      set(value) {
        const data = { rootGroup: value };
        this.$store.dispatch("browser/settingChanged", data);
      },
    },
  },
};
</script>

// style is handled in browser-filter-toolbar.vue
