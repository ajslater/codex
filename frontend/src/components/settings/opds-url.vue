<template>
  <div class="opdsVersion" :title="tooltip" @click="onClickURL">
    <h3>
      {{ title }}
      <span v-if="clipBoardEnabled">
        <v-icon class="clipBoardIcon" size="small">
          {{ clipBoardIcon }}
        </v-icon>
        <v-fade-transition>
          <span v-show="showTooltip.show" class="copied">Copied</span>
        </v-fade-transition>
      </span>
      <span v-if="subtitle" class="subtitle">
        {{ subtitle }}
      </span>
    </h3>
    <div class="opdsUrl">
      {{ url }}
    </div>
  </div>
</template>
<script>
import { mdiClipboardCheckOutline, mdiClipboardOutline, mdiRss } from "@mdi/js";

import { copyToClipboard } from "@/copy-to-clipboard";

const TOOLTIP = "Copy OPDS URL to clipboard";

export default {
  name: "OPDSUrl",
  props: {
    title: {
      type: String,
      required: true,
    },
    subtitle: {
      type: String,
      default: undefined,
    },
    urlPath: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      mdiRss,
      showTooltip: { show: false },
    };
  },
  computed: {
    clipBoardEnabled() {
      return location.protocol == "https:";
    },
    clipBoardIcon() {
      return this.showTooltip.show
        ? mdiClipboardCheckOutline
        : mdiClipboardOutline;
    },
    tooltip() {
      return TOOLTIP ? this.clipBoardEnabled : undefined;
    },
    url() {
      return globalThis.origin + this.urlPath;
    },
  },
  methods: {
    onClickURL() {
      if (!this.clipBoardEnabled) {
        return;
      }
      copyToClipboard(this.url, this.showTooltip);
    },
  },
};
</script>
<style scoped lang="scss">
.copied {
  font-size: small;
  font-weight: normal;
  color: rgb(var(--v-theme-textSecondary));
}
.clipBoardIcon {
  color: rgb(var(--v-theme-iconsInactive));
}
.opdsVersion {
  padding: 5px;
}
.opdsVersion:hover {
  background-color: rgb(var(--v-theme-surface));
}
.opdsVersion:hover .clipBoardIcon,
.opdsVersion:hover .opdsUrl {
  color: rgb(var(--v-theme-textPrimary));
}
.opdsUrl {
  color: rgb(var(--v-theme-textSecondary));
}
.subtitle {
  font-size: 12px;
  font-weight: normal;
  color: rgb(var(--v-theme-textDisabled));
}
</style>
