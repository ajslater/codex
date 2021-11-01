<template>
  <v-dialog
    class="readerKeyboardShortcuts"
    origin="center top"
    transition="slide-y-transition"
    overlay-opacity="0.5"
    width="fit-content"
  >
    <template #activator="{ on }">
      <v-btn icon v-on="on">
        <v-icon>{{ mdiKeyboard }}</v-icon>
      </v-btn>
    </template>
    <div id="readerKeyboardShortcutsDialog">
      <h2>Keyboard Shortcuts</h2>
      <table id="readerKeyboardShortcutsTable">
        <tbody>
          <tr>
            <td>?</td>
            <td>This help dialog</td>
          </tr>
          <tr>
            <td>
              <v-icon>{{ mdiMenuLeft }}</v-icon>
            </td>
            <td>Previous page</td>
          </tr>
          <tr>
            <td>
              <v-icon>{{ mdiMenuRight }}</v-icon>
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
            <td>esc</td>
            <td>Close book</td>
          </tr>
        </tbody>
      </table>
    </div>
  </v-dialog>
</template>

<script>
import { mdiCog, mdiKeyboard, mdiMenuLeft, mdiMenuRight } from "@mdi/js";

export default {
  data() {
    return {
      mdiCog,
      mdiKeyboard,
      mdiMenuLeft,
      mdiMenuRight,
    };
  },
  mounted() {
    document.addEventListener("?", this._keyListener);
  },
  beforeDestroy() {
    document.removeEventListener("?", this._keyListener);
  },
  methods: {
    _keyListener: function (event) {
      // XXX Hack to get around too many listeners being added.
      event.stopPropagation();

      if (event.key === "h") {
        console.log("OPEN MENU");
      }
    },
  },
};
</script>

<style scoped lang="scss">
#readerKeyboardShortcutsDialog {
  padding: 20px;
}
#readerKeyboardShortcutsTable {
  margin-top: 10px;
  border-collapse: collapse;
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
/* eslint-disable-next-line vue-scoped-css/no-unused-selector */
.v-dialog {
  /* Seems like I'm fixing a bug here */
  background-color: #121212;
}
</style>
