<template>
  <v-hover v-slot="{ hover }">
    <v-select
      v-model="topGroup"
      class="toolbarSelect topGroupSelect"
      :items="topGroupChoices"
      dense
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
</template>

<script>
import { mapActions, mapGetters, mapState } from "vuex";

export default {
  name: "BrowserTopGroupSelect",
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
        if (
          (this.topGroupSetting === "f" && value !== "f") ||
          (this.topGroupSetting !== "f" && value === "f")
        ) {
          this.$router.push({ params: { group: value, pk: 0 } });
        }
        // This must happen after the push
        const settings = { topGroup: value };
        this.settingChanged(settings);
      },
    },
  },
  methods: {
    ...mapActions("browser", ["settingChanged"]),
  },
};
</script>

// #topGroupSelect style is handled in browser-filter-toolbar.vue
