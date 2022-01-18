<template>
  <div v-if="!isMobile()" id="readerKeyboardShortcutsDialog">
    <h3>Keyboard Shortcuts</h3>
    <table id="readerKeyboardShortcutsTable">
      <tbody>
        <tr>
          <td>
            <v-icon>{{ mdiMenuLeft }}</v-icon
            >j
          </td>
          <td>Previous page</td>
        </tr>
        <tr>
          <td>
            <v-icon>{{ mdiMenuRight }}</v-icon
            >k
          </td>
          <td>Next page</td>
        </tr>
        <tr>
          <td>h</td>
          <td>Shrink page to screen height</td>
        </tr>
        <tr>
          <td>w</td>
          <td>Shrink page to screen width</td>
        </tr>
        <tr>
          <td>o</td>
          <td>Expand page to original size</td>
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
import { mdiMenuLeft, mdiMenuRight } from "@mdi/js";

export default {
  data() {
    return {
      mdiMenuLeft,
      mdiMenuRight,
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
  margin-top: 5px;
  padding: 15px;
}
#readerKeyboardShortcutsTable {
  margin-top: 10px;
  border-collapse: collapse;
  color: gray;
}
#readerKeyboardShortcutsTable td {
  min-width: 42px;
}
#readerKeyboardShortcutsTable tr:nth-child(odd) {
  background-color: #222;
}
#readerKeyboardShortcutsTable td {
  padding: 5px;
}
#readerKeyboardShortcutsTable td:first-child {
  text-align: center;
}
</style>
