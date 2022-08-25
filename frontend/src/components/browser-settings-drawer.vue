<template>
  <v-navigation-drawer
    id="browserSettingsDrawer"
    v-model="isSettingsDrawerOpen"
    app
    right
    temporary
    touchless
  >
    <div v-if="isOpenToSee">
      <div id="browserSettings">
        <h3>Browser Settings</h3>
        <div class="settingsGroupCaption text-caption">
          Show these groups when navigating the browse hierarchy.
        </div>
        <v-checkbox
          v-for="choice of groupChoices"
          :key="choice.text"
          :input-value="showSettings[choice.value]"
          :label="`Show ${choice.text}`"
          dense
          class="settingsCheckbox"
          @change="setShow(choice.value, $event)"
        />
      </div>
      <v-divider />
      <SearchHelp />
    </div>
    <SettingsCommonPanel />
  </v-navigation-drawer>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapActions, mapGetters, mapMutations, mapState } from "vuex";

import SearchHelp from "@/components/browser-search-help.vue";
import SettingsCommonPanel from "@/components/settings-common-panel.vue";

export default {
  name: "BrowserSettingsDialog",
  components: { SearchHelp, SettingsCommonPanel },
  data() {
    return {
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapGetters("auth", ["isOpenToSee"]),
    ...mapState("browser", {
      groupChoices: (state) => state.formChoices.settingsGroup,
      showSettings: (state) => state.settings.show,
    }),
    isSettingsDrawerOpen: {
      get() {
        return this.$store.state.browser.isSettingsDrawerOpen;
      },
      set(value) {
        this.setIsSettingsDrawerOpen(value);
      },
    },
  },
  mounted() {
    this.$emit("panelMounted");
  },
  methods: {
    ...mapActions("browser", ["settingChanged"]),
    ...mapMutations("browser", ["setIsSettingsDrawerOpen"]),
    setShow: function (group, value) {
      const data = { show: { [group]: value === true } };
      this.settingChanged(data);
    },
  },
};
</script>

<style scoped lang="scss">
#browserSettingsDrawer {
  background-color: #121212;
  z-index: 20;
}
#browserSettings {
  padding-top: 10px;
  padding-left: 15px;
  padding-right: env(safe-area-inset-right);
}
.settingsGroupCaption {
  color: gray;
}
.settingsCheckbox {
  padding-left: 5px;
}
</style>
