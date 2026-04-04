<template>
  <div class="clipboard" :title="tooltipText" @click.stop="onClick">
    <span class="clipboardTitle">
      {{ title }}
      <span v-if="isSupported" class="iconContainer">
        <v-icon class="clipboardIcon" size="small" :icon="icon" />
        <v-fade-transition>
          <span v-show="copied" class="copied">Copied</span>
        </v-fade-transition>
      </span>
    </span>
    <span v-if="subtitle" class="subtitle">{{ subtitle }}</span>
    <div class="bodyText">{{ text }}</div>
  </div>
</template>
<script>
import { useClipboard } from "@vueuse/core";
import { mdiClipboardCheckOutline, mdiClipboardOutline } from "@mdi/js";

export default {
  name: "ClipBoard",
  props: {
    tooltip: { type: String, required: true },
    title: { type: String, required: true },
    subtitle: { type: String, default: "" },
    text: { type: String, required: true },
  },
  setup(props) {
    const { copy, copied, isSupported } = useClipboard({
      source: () => props.text,
      copiedDuring: 5000,
    });
    return { copy, copied, isSupported };
  },
  computed: {
    tooltipText() {
      return this.isSupported ? this.tooltip : undefined;
    },
    icon() {
      return this.copied ? mdiClipboardCheckOutline : mdiClipboardOutline;
    },
  },
  methods: {
    onClick() {
      if (this.isSupported) {
        this.copy().catch(console.warn);
      }
    },
  },
};
</script>
<style scoped lang="scss">
.clipboard:hover {
  background-color: rgb(var(--v-theme-surface));
}

.clipboardTitle {
  font-size: larger;
  font-weight: bolder;
}

.subtitle {
  padding-left: 0.5em;
  font-size: small;
  font-weight: normal;
  color: rgb(var(--v-theme-textDisabled));
}

.copied {
  font-size: small;
  font-weight: normal;
  color: rgb(var(--v-theme-textSecondary));
}

.clipboardIcon {
  color: rgb(var(--v-theme-iconsInactive));
}

.bodyText {
  color: rgb(var(--v-theme-textSecondary));
}

.clipboard:hover .clipboardIcon,
.clipboard:hover .bodyText {
  color: rgb(var(--v-theme-textPrimary)) !important;
}
</style>
