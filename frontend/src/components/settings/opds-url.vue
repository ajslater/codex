<template>
  <div
    class="opdsVersion"
    title="Copy OPDS URL to Clipboard"
    @click="onClickURL"
  >
    <h3>
      {{ title }}
      <v-icon class="clipBoardIcon" size="small">
        {{ clipBoardIcon }}
      </v-icon>
      <v-fade-transition>
        <span v-show="showTooltip.show" class="copied">Copied</span>
      </v-fade-transition>
    </h3>
    <div v-if="subtitle" class="subtitle">
      {{ subtitle }}
    </div>
    <div class="opdsUrl">{{ url }}</div>
  </div>
</template>
<script>
import { mdiClipboardCheckOutline, mdiClipboardOutline, mdiRss } from "@mdi/js";

import { copyToClipboard } from "@/copy-to-clipboard";

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
    url: {
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
    clipBoardIcon() {
      return this.showTooltip.show
        ? mdiClipboardCheckOutline
        : mdiClipboardOutline;
    },
  },
  methods: {
    onClickURL() {
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
  font-size: smaller;
  color: rgb(var(--v-theme-textSecondary));
}
</style>
