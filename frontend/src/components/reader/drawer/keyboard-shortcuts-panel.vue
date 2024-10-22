<template>
  <v-expansion-panels v-if="!IS_MOBILE">
    <v-expansion-panel id="readerKeyboardShortcuts">
      <v-expansion-panel-title id="shortcutsTitle">
        <CodexListItem
          id="keyboardShortcutsItem"
          :prepend-icon="mdiKeyboardOutline"
          title="Keyboard Shortcuts"
        />
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <KeyboardShortcutsTable />
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script>
import { mdiKeyboardOutline } from "@mdi/js";

import CodexListItem from "@/components/codex-list-item.vue";
import KeyboardShortcutsTable from "@/components/reader/drawer/keyboard-shortcuts-table.vue";
import { IS_MOBILE } from "@/platform";

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "KeyboardShortcutsPanel",
  components: {
    CodexListItem,
    KeyboardShortcutsTable,
  },
  data() {
    return {
      mdiKeyboardOutline,
      IS_MOBILE,
    };
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

#keyboardShortcutsItem {
  padding-left: 0px;
}

:deep(.v-expansion-panel-title--active) {
  min-height: 48px !important;
}

:deep(.v-expansion-panel-text__wrapper) {
  padding-left: 10px;
  padding-right: 10px;
}
</style>
