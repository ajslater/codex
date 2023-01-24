<template>
  <v-dialog max-width="30em">
    <template #activator="{ props }">
      <v-btn id="opdsButton" icon size="small" variant="plain" v-bind="props">
        <v-icon>{{ mdiRss }}</v-icon>
        OPDS
      </v-btn>
    </template>
    <div id="opds">
      <h2>
        <v-icon size="x=small" class="inline">{{ mdiRss }}</v-icon>
        OPDS
      </h2>
      <div
        id="opdsv1"
        title="Copy OPDS URL to Clipboard"
        @click="copyToClipboard"
      >
        <h3>
          v1.2
          <v-icon id="clipBoardIcon" size="small">
            {{ clipBoardIcon }}
          </v-icon>
          <v-fade-transition>
            <span v-show="showTool" id="copied"> Copied </span>
          </v-fade-transition>
        </h3>
        <div id="opdsUrl">{{ opdsURL }}</div>
      </div>
    </div>
  </v-dialog>
</template>
<script>
import { mdiClipboardCheckOutline, mdiClipboardOutline, mdiRss } from "@mdi/js";

export default {
  name: "OPDSDialog",
  data() {
    return {
      mdiRss,
      opdsURL: window.origin + window.CODEX.OPDS_PATH,
      showTool: false,
    };
  },
  computed: {
    clipBoardIcon() {
      return this.showTool ? mdiClipboardCheckOutline : mdiClipboardOutline;
    },
  },
  methods: {
    copyToClipboard() {
      navigator.clipboard
        .writeText(this.opdsURL)
        .then(() => {
          this.showTool = true;
          setTimeout(() => {
            this.showTool = false;
          }, 5000);
          return true;
        })
        .catch(console.warn);
    },
  },
};
</script>
<style scoped lang="scss">
#opds {
  padding: 20px;
}
#opdsButton {
  color: rgb(var(--v-theme-textSecondary));
}
.inline {
  display: inline-flex;
}
#copied {
  font-size: small;
  font-weight: normal;
  color: rgb(var(--v-theme-textSecondary));
}
#clipBoardIcon {
  color: rgb(var(--v-theme-iconsInactive));
}
#opdsv1 {
  padding: 5px;
}
#opdsv1:hover {
  background-color: rgb(var(--v-theme-surface));
}
#opdsv1:hover #clipBoardIcon,
#opdsv1:hover #opdsUrl {
  color: rgb(var(--v-theme-textPrimary));
}
#opdsUrl {
  color: rgb(var(--v-theme-textSecondary));
}
</style>
