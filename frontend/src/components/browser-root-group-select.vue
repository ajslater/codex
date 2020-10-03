<template>
  <v-select
    v-model="rootGroup"
    :items="rootGroupChoices"
    class="toolbarSelect rootGroupSelect"
    dense
    hide-details="auto"
    ripple
  />
</template>

<script>
import { mapGetters, mapState } from "vuex";
export default {
  name: "BrowserRootGroupSelect",
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

<style scoped lang="scss">
.rootGroupSelect {
  width: 118px;
  margin-left: 8px;
  margin-right: 8px;
}
@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  .rootGroupSelect {
    width: 95px;
    margin-left: 4px;
    margin-right: 4px;
  }
}
</style>
