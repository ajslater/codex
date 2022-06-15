<template>
  <div>
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
    <v-list-item :href="searchHelpURL" target="_blank" ripple>
      <v-list-item-content>
        <v-list-item-title
          >Search Syntax Help
          <v-icon class="openInNewIcon">{{
            mdiOpenInNew
          }}</v-icon></v-list-item-title
        >
      </v-list-item-content>
    </v-list-item>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapActions, mapMutations, mapState } from "vuex";

export default {
  name: "BrowserSettingsDialog",
  data() {
    return {
      mdiOpenInNew,
      searchHelpURL: "https://github.com/ajslater/codex/blob/release/SEARCH.md",
    };
  },
  computed: {
    ...mapState("browser", {
      groupChoices: (state) => state.formChoices.settingsGroup,
      showSettings: (state) => state.settings.show,
      isSettingsDrawerOpen: (state) => state.isSettingsDrawerOpen,
    }),
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
.settingsGroupCaption {
  color: gray;
}
.settingsCheckbox {
  padding-left: 5px;
}
#browserSettings {
  padding-left: 15px;
}
.openInNewIcon {
  color: gray;
}
</style>
