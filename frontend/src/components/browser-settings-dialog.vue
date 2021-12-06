<template>
  <v-dialog
    v-model="dialogVisible"
    origin="center-top"
    transition="slide-y-transition"
    max-width="20em"
    overlay-opacity="0.5"
    @focus="focus()"
  >
    <template #activator="{ on }">
      <v-list-item v-if="isOpenToSee" v-on="on">
        <v-list-item-content>
          <v-list-item-title> Settings </v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </template>
    <div id="browserSettingsDialog">
      <h3>Browser Settings</h3>
      <div class="settingsGroupCaption text-caption">
        Show these groups when navigating the browse hierarchy.
      </div>
      <v-checkbox
        v-for="choice of groupChoices"
        :key="choice.value"
        :input-value="getShow(choice.value)"
        :label="`Show ${choice.text}`"
        dense
        @change="setShow(choice.value, $event)"
      />
      <VersionsFooter />
    </div>
  </v-dialog>
</template>

<script>
import { mapGetters, mapState } from "vuex";

import VersionsFooter from "@/components/version-footer";

export default {
  name: "BrowserSettingsDialog",
  components: {
    VersionsFooter,
  },
  data() {
    return {
      dialogVisible: false,
    };
  },
  computed: {
    ...mapState("browser", {
      groupChoices: (state) => state.formChoices.settingsGroup,
      showSettings: (state) => state.settings.show,
    }),
    ...mapGetters("auth", ["isOpenToSee"]),
  },
  watch: {
    dialogVisible: function (to) {
      if (to) {
        this.focus();
      }
    },
  },
  methods: {
    getShow: function (group) {
      return this.showSettings[group];
    },
    setShow: function (group, value) {
      const data = { show: { [group]: value === true } };
      this.$store.dispatch("browser/settingChanged", data);
    },
    focus: function () {
      this.$emit("sub-dialog-open");
    },
  },
};
</script>

<style scoped lang="scss">
.settingsGroupCaption {
  color: gray;
}
#browserSettingsDialog {
  padding: 20px;
}
</style>
