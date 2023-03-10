<template>
  <v-expansion-panels v-if="!isMobile">
    <v-expansion-panel id="readerKeyboardShortcuts">
      <v-expansion-panel-title id="shortcutsTitle">
        <v-icon id="keyboardIcon">{{ mdiKeyboardOutline }}</v-icon
        >Keyboard Shortcuts
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <h4>Navigation</h4>
        <table class="highlight-table">
          <tbody>
            <tr>
              <td>
                <v-icon class="keyIcon" density="compact">
                  {{ mdiMenuLeft }} </v-icon
                >, j,
                <div>
                  <v-icon class="keyIcon" density="compact">
                    {{ mdiAppleKeyboardShift }}
                  </v-icon>
                  <v-icon class="keyIcon" density="compact">
                    {{ mdiKeyboardSpace }}
                  </v-icon>
                </div>
              </td>
              <td>Previous page</td>
            </tr>
            <tr>
              <td>
                <v-icon class="keyIcon" density="compact">
                  {{ mdiMenuRight }} </v-icon
                >, k,
                <v-icon class="keyIcon" density="compact">
                  {{ mdiKeyboardSpace }}
                </v-icon>
              </td>
              <td>Next page</td>
            </tr>
            <tr>
              <td>,</td>
              <td>Next <em>only</em> one page in two page mode.</td>
            </tr>
            <tr>
              <td>.</td>
              <td>Previous <em>only</em> one page in two page mode.</td>
            </tr>
            <tr>
              <td>p</td>
              <td>Previous Book</td>
            </tr>
            <tr>
              <td>n</td>
              <td>Next Book</td>
            </tr>
          </tbody>
        </table>
        <h4>Fit Page To</h4>
        <table class="highlight-table">
          <tbody>
            <tr>
              <td>s</td>
              <td>screen</td>
            </tr>
            <tr>
              <td>h</td>
              <td>screen height</td>
            </tr>
            <tr>
              <td>w</td>
              <td>screen width</td>
            </tr>
            <tr>
              <td>o</td>
              <td>Show page at original size</td>
            </tr>
            <tr>
              <td>2</td>
              <td>Toggle two page view</td>
            </tr>
            <tr>
              <td>r</td>
              <td>Toggle Read in Reverse</td>
            </tr>
          </tbody>
        </table>
        <h4>Other</h4>
        <table class="highlight-table">
          <tbody>
            <tr>
              <td>m</td>
              <td>Show comic's metadata</td>
            </tr>
            <tr>
              <td>esc</td>
              <td>Close book</td>
            </tr>
          </tbody>
        </table>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script>
import {
  mdiAppleKeyboardShift,
  mdiKeyboardOutline,
  mdiKeyboardSpace,
  mdiMenuLeft,
  mdiMenuRight,
} from "@mdi/js";
import { mapGetters } from "pinia";

import { useCommonStore } from "@/stores/common";

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "KeyboardShortcutsPanel",
  data() {
    return {
      mdiMenuLeft,
      mdiMenuRight,
      mdiKeyboardOutline,
      mdiKeyboardSpace,
      mdiAppleKeyboardShift,
    };
  },
  computed: {
    ...mapGetters(useCommonStore, ["isMobile"]),
  },
};
</script>

<style scoped lang="scss">
#readerKeyboardShortcuts {
  background-color: rgb(var(--v-theme-background));
}
#shortcutsTitle {
  padding: 0;
  padding-left: 17px;
  padding-right: 10px;
  font-size: 16px;
}
#keyboardIcon {
  margin-right: 0.33em !important;
  color: rgb(var(--v-theme-textDisabled));
}
:deep(.v-expansion-panel-title--active) {
  min-height: 48px !important;
}
:deep(.v-expansion-panel-text__wrapper) {
  padding-left: 10px;
  padding-right: 10px;
}
.highlight-table {
  margin-top: 10px;
  border-collapse: collapse;
  color: rgb(var(--v-theme-textDisabled));
}
h4 {
  padding-left: 0.5em;
  color: rgb(var(--v-theme-textSecondary));
}
.highlight-table tr:nth-child(odd) {
  background-color: rgb(var(--v-theme-surface)) !important;
}
.highlight-table td {
  min-width: 60px;
  padding: 5px;
}
.highlight-table td:first-child {
  text-align: center;
}
.keyIcon {
  margin: 0;
}
</style>
