<template>
  <div class="settingsHeader">Navigation</div>
  <v-table class="shortcutsTable" striped="odd">
    <tbody>
      <tr>
        <td>
          <v-hotkey keys="j" />, <v-hotkey keys="arrowleft" />,
          <v-hotkey keys="shift+space" />
        </td>
        <td>Previous page</td>
      </tr>
      <tr>
        <td>
          <v-hotkey keys="k" />, <v-hotkey keys="arrowright" />,
          <v-hotkey keys="space" />
        </td>
        <td>Next page</td>
      </tr>
      <tr>
        <td><v-hotkey keys="," /></td>
        <td>Next <em>only</em> one page in two page mode.</td>
      </tr>
      <tr>
        <td><v-hotkey keys="." /></td>
        <td>Previous <em>only</em> one page in two page mode.</td>
      </tr>
      <tr>
        <td><v-hotkey keys="p" /></td>
        <td>Previous Book</td>
      </tr>
      <tr>
        <td><v-hotkey keys="n" /></td>
        <td>Next Book</td>
      </tr>
      <tr>
        <td><v-hotkey keys="esc" /></td>
        <td>Close book</td>
      </tr>
    </tbody>
  </v-table>
  <div class="settingsHeader">Fit Page To</div>
  <v-table class="shortcutsTable" striped="odd">
    <tbody>
      <tr>
        <td><v-hotkey keys="s" /></td>
        <td>Screen</td>
      </tr>
      <tr>
        <td>
          <v-hotkey keys="h" />
        </td>
        <td>Screen height</td>
      </tr>
      <tr>
        <td><v-hotkey keys="w" /></td>
        <td>Screen width</td>
      </tr>
      <tr>
        <td><v-hotkey keys="o" /></td>
        <td>Show page at original size</td>
      </tr>
      <tr>
        <td><v-hotkey keys="2" /></td>
        <td>Toggle two page view</td>
      </tr>
      <tr>
        <td><v-hotkey keys="r" /></td>
        <td>Read Right to Left</td>
      </tr>
      <tr>
        <td><v-hotkey keys="l" /></td>
        <td>Read Left to Right</td>
      </tr>
      <tr>
        <td><v-hotkey keys="t" /></td>
        <td>Read Top to Bottom</td>
      </tr>
      <tr>
        <td><v-hotkey keys="b" /></td>
        <td>Read in Bottom to Top</td>
      </tr>
    </tbody>
  </v-table>
  <div class="settingsHeader">Other</div>
  <v-table class="shortcutsTable" striped="odd">
    <tbody>
      <tr>
        <td><v-hotkey keys="m" /></td>
        <td>Show comic's metadata</td>
      </tr>
      <tr>
        <td><v-hotkey keys="doubleclick" /></td>
        <td>Zoom page</td>
      </tr>
    </tbody>
  </v-table>
</template>
<script>
import {
  mdiAppleKeyboardShift,
  mdiKeyboardSpace,
  mdiMenuLeft,
  mdiMenuRight,
} from "@mdi/js";
export default {
  name: "KeyboardShortcutsTable",
  data() {
    return {
      mdiMenuLeft,
      mdiMenuRight,
      mdiKeyboardSpace,
      mdiAppleKeyboardShift,
    };
  },
};
</script>

<style scoped lang="scss">
.settingsHeader {
  padding-top: 10px;
  padding-left: 15px;
  padding-right: 10px;
  font-weight: bolder;
  color: rgb(var(--v-theme-textSecondary));
}

:deep(.v-expansion-panel-title--active) {
  min-height: 48px !important;
}

:deep(.v-expansion-panel-text__wrapper) {
  padding-left: 10px;
  padding-right: 10px;
}

.shortcutsTable {
  margin-top: 10px;
  background-color: inherit;
  color: rgb(var(--v-theme-textDisabled));
}

.shortcutsTable td {
  padding: 5px;
}

.shortcutsTable td:first-child {
  width: 105px;
}

.keyIcon {
  margin: 0;
}
</style>
