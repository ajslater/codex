<template>
  <v-dialog v-model="dialog" fullscreen transition="dialog-bottom-transition">
    <template #activator="{ props: activatorProps }">
      <MetadataActivator
        v-bind="activatorProps"
        :book="book"
        :toolbar="toolbar"
      />
    </template>
    <CloseButton
      class="closeButton"
      title="Close Metadata (esc)"
      @click="dialog = false"
    />
    <div
      v-if="showContainer"
      id="metadataContainer"
      @keyup.esc="dialog = false"
    >
      <MetadataHeader :group="book.group" />
      <MetadataBody :book="book" />
    </div>
    <div v-else id="placeholderContainer">
      <div id="placeholderTitle">Tags Loading</div>
      <PlaceholderLoading
        :model-value="progress"
        :indeterminate="progress >= 100"
        class="placeholder"
      />
    </div>
  </v-dialog>
</template>

<script>
import { mapActions, mapState } from "pinia";

import CloseButton from "@/components/close-button.vue";
import MetadataActivator from "@/components/metadata/metadata-activator.vue";
import MetadataBody from "@/components/metadata/metadata-body.vue";
import MetadataHeader from "@/components/metadata/metadata-header.vue";
import PlaceholderLoading from "@/components/placeholder-loading.vue";
import { useMetadataStore } from "@/stores/metadata";

/*
 * Progress circle
 * Can take 19 seconds for 22k children
 */
const CHILDREN_PER_SECOND = 1160;
const MIN_SECS = 0.05;
const UPDATE_INTERVAL = 250;

export default {
  name: "MetadataButton",
  components: {
    CloseButton,
    MetadataActivator,
    MetadataBody,
    MetadataHeader,
    PlaceholderLoading,
  },
  props: {
    book: {
      type: Object,
      required: true,
    },
    toolbar: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      dialog: false,
      progress: 0,
    };
  },
  computed: {
    ...mapState(useMetadataStore, {
      md: (state) => state.md,
    }),
    showContainer() {
      return this.md?.loaded || false;
    },
    children() {
      return this.book.childCount || 0;
    },
  },
  watch: {
    dialog(to) {
      if (to) {
        this.dialogOpened();
      } else {
        this.clearMetadata();
      }
    },
  },
  methods: {
    ...mapActions(useMetadataStore, ["clearMetadata", "loadMetadata"]),
    dialogOpened() {
      const pks = this.book.ids || [this.book.pk];
      const data = {
        group: this.book.group,
        pks,
      };
      this.loadMetadata(data);
      this.startProgress();
    },
    startProgress() {
      this.startTime = Date.now();
      this.estimatedMS =
        Math.max(MIN_SECS, this.children / CHILDREN_PER_SECOND) * 1000;
      this.updateProgress();
    },
    updateProgress() {
      const elapsed = Date.now() - this.startTime;
      this.progress = (elapsed / this.estimatedMS) * 100;
      if (this.progress >= 100 || this.md) {
        return;
      }
      setTimeout(() => {
        this.updateProgress();
      }, UPDATE_INTERVAL);
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

.closeButton {
  position: fixed;
  top: 0px;
  right: 0px;
  opacity: 0.5;
}

#metadataContainer {
  display: flex;
  flex-direction: column;
  max-width: 100vw;
  overflow-y: auto !important;
}

#placeholderContainer {
  min-height: 100%;
  min-width: 100%;
  text-align: center;
}

#placeholderTitle {
  font-size: xx-large;
  color: rgb(var(--v-theme-textDisabled));
}

#metadataContainer,
#placeholderContainer {
  padding-top: max(20px, env(safe-area-inset-top));
  padding-left: max(20px, env(safe-area-inset-left));
  padding-right: max(20px, env(safe-area-inset-right));
  padding-bottom: max(20px, env(safe-area-inset-bottom));
}

.placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #metadataContainer {
    font-size: 12px;
  }
}
</style>
