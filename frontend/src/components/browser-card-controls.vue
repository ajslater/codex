<template>
  <div class="linkSpacer">
    <v-icon v-if="item.group === 'c'" class="eye">
      {{ eyeIcon }}
    </v-icon>
    <MetadataButton
      class="metadataButton"
      :group="item.group"
      :pk="item.pk"
      :children="item.childCount"
    />
    <BrowserCardMenu
      class="browserCardMenu"
      :group="item.group"
      :pk="item.pk"
      :finished="item.finished"
    />
  </div>
</template>

<script>
import { mdiEye, mdiEyeOff } from "@mdi/js";

import BrowserCardMenu from "@/components/browser-card-menu";
import MetadataButton from "@/components/metadata-dialog";
export default {
  name: "BrowserCardControls",
  components: {
    BrowserCardMenu,
    MetadataButton,
  },
  props: {
    item: {
      type: Object,
      required: true,
    },
    eyeOpen: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      mdiEye,
      mdiEyeOff,
    };
  },
  computed: {
    eyeIcon: function () {
      return this.eyeOpen ? mdiEye : mdiEyeOff;
    },
  },
};
</script>

<style scoped lang="scss">
@import "~vuetify/src/styles/styles.sass";
@import "book-cover.scss";
.linkSpacer {
  height: 100%;
  width: 100%;
  opacity: 0; // invisible by default. hover exposes it.
}
.eye {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translateX(-50%) translateY(-50%);
}
</style>
<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
$button-margin: 5px;
.tagIcon {
  position: absolute !important;
  left: $button-margin !important;
  bottom: $button-margin !important;
}
.browserCardMenuIcon {
  position: absolute !important;
  right: $button-margin !important;
  bottom: $button-margin !important;
}

@import "~vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  $small-button-margin: 5px;
  .tagIcon {
    left: $small-button-margin !important;
    bottom: $small-button-margin !important;
  }
  .browserCardMenuIcon {
    right: $small-button-margin !important;
    bottom: $small-button-margin !important;
  }
}
</style>
