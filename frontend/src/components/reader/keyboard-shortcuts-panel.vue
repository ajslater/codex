<template>
  <div v-if="!isMobile()" id="readerKeyboardShortcutsDialog">
    <h3>Keyboard Shortcuts</h3>
    <table id="readerKeyboardShortcutsTable" class="highlight-table">
      <tbody>
        <tr>
          <td>
            <v-icon color="grey">
              {{ mdiMenuLeft }}
            </v-icon>
            j<br />
            <v-icon color="grey" dense>
              {{ mdiAppleKeyboardShift }}
            </v-icon>
            <v-icon color="grey" dense>
              {{ mdiKeyboardSpace }}
            </v-icon>
          </td>
          <td>Previous page</td>
        </tr>
        <tr>
          <td>
            <v-icon color="grey"> {{ mdiMenuRight }} </v-icon>k<br />
            <v-icon color="grey" dense>
              {{ mdiKeyboardSpace }}
            </v-icon>
          </td>
          <td>Next page</td>
        </tr>
        <tr>
          <td>h</td>
          <td>Fit page to screen height</td>
        </tr>
        <tr>
          <td>w</td>
          <td>Fit page to screen width</td>
        </tr>
        <tr>
          <td>s</td>
          <td>Fit page to screen</td>
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
          <td>m</td>
          <td>Show comic's metadata</td>
        </tr>
        <tr>
          <td>c</td>
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

export default {
  data() {
    return {
      mdiMenuLeft,
      mdiMenuRight,
      mdiKeyboardSpace,
      mdiAppleKeyboardShift,
    };
  },
  methods: {
    isMobile: function () {
      // Probably janky mobile detection
      return (
        typeof window.orientation !== "undefined" ||
        navigator.userAgent.includes("IEMobile")
      );
    },
  },
};
</script>

<style scoped lang="scss">
#readerKeyboardShortcutsDialog {
  padding: 15px;
}
#readerKeyboardShortcutsTable {
  margin-top: 10px;
  border-collapse: collapse;
  color: gray;
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
</style>
