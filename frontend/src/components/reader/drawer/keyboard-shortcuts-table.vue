<template>
  <h4>Navigation</h4>
  <table class="highlight-table">
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
  </table>
  <h4>Fit Page To</h4>
  <table class="highlight-table">
    <tbody>
      <tr>
        <td><v-hotkey keys="s" /></td>
        <td>screen</td>
      </tr>
      <tr>
        <td>
          <v-hotkey keys="h" />
        </td>
        <td>screen height</td>
      </tr>
      <tr>
        <td><v-hotkey keys="w" /></td>
        <td>screen width</td>
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
  </table>
  <h4>Other</h4>
  <table class="highlight-table">
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
  </table>
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
