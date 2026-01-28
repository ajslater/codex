<template>
  <span class="clipboard" :title="tooltipText" @click.stop="onClick">
    <h3>
      {{ title }}
      <span v-if="enabled" class="iconContainer">
        <v-icon class="clipboardIcon" size="small" :icon="icon" />
        <v-fade-transition>
          <span v-show="showTooltip.show" class="copied">Copied</span>
        </v-fade-transition>
      </span>
      <span v-if="subtitle" class="subtitle">{{ subtitle }}</span>
    </h3>
    <div class="bodyText">{{ text }}</div>
  </span>
  <slot />
</template>
<script>
import { mdiClipboardCheckOutline, mdiClipboardOutline } from "@mdi/js";

export default {
  name: "ClipBoard",
  props: {
    tooltip: { type: String, required: true },
    title: { type: String, required: true },
    subtitle: { type: String, required: true },
    text: { type: String, required: true },
  },
  data() {
    return {
      showTooltip: { show: false },
    };
  },
  computed: {
    enabled() {
      return true || location.protocol == "https:";
    },
    tooltipText() {
      return this.enabled ? this.tooltip : undefined;
    },
    icon() {
      return this.showTooltip.show
        ? mdiClipboardCheckOutline
        : mdiClipboardOutline;
    },
  },
  methods: {
    onClick() {
      if (!this.enabled) {
        return;
      }
      navigator.clipboard
        .writeText(this.text)
        .then(() => {
          this.showTooltip.show = true;
          setTimeout(() => {
            this.showTooltip.show = false;
          }, 5000);
          return true;
        })
        .catch(console.warn);
    },
  },
};
</script>
<style scoped lang="scss">
.clipboard:hover {
  background-color: rgb(var(--v-theme-surface));
}

.subtitle {
  font-size: 12px;
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
