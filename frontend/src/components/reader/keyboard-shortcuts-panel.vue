<template>
  <div v-if="!isMobile" id="readerKeyboardShortcutsDialog">
    <h3>Keyboard Shortcuts</h3>
    <table id="readerKeyboardShortcutsTable" class="highlight-table">
      <tbody>
        <tr>
          <th colspan="2">Navigation</th>
        </tr>
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
        <tr>
          <th colspan="2">Fit Page To</th>
        </tr>
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
  </div>
</template>

<script>
import {
  mdiAppleKeyboardShift,
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
#readerKeyboardShortcutsDialog {
  padding: 15px;
  background-color: rgb(var(--v-theme-background));
}
#readerKeyboardShortcutsTable {
  margin-top: 10px;
  border-collapse: collapse;
  color: rgb(var(--v-theme-textDisabled));
}
#readerKeyboardShortcutsTable th {
  padding-left: 1em;
  text-align: left;
}
#readerKeyboardShortcutsTable tr:nth-child(odd) {
  background-color: rgb(var(--v-theme-surface)) !important;
}
#readerKeyboardShortcutsTable td {
  min-width: 60px;
}
#readerKeyboardShortcutsTable td {
  padding: 5px;
}
#readerKeyboardShortcutsTable td:first-child {
  text-align: center;
}
.keyIcon {
  margin: 0;
}
</style>
