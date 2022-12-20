<template>
  <div class="cardControls">
    <v-icon v-if="item.group === 'c'" class="eye">
      {{ eyeIcon }}
    </v-icon>
    <MetadataButton
      :group="item.group"
      :pk="item.pk"
      :children="item.childCount"
    />
    <BrowserCardMenu :item="item" />
  </div>
</template>

<script>
import { mdiEye, mdiEyeOff } from "@mdi/js";

import BrowserCardMenu from "@/components/browser/card/browser-card-menu.vue";
import MetadataButton from "@/components/metadata/metadata-dialog.vue";
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
@import "../../book-cover.scss";
.cardControls {
  height: 100%;
  width: 100%;
  opacity: 0; // invisible by default. hover exposes it.
}
$buttonColor: rgb(var(--v-theme-textSecondary));
$buttonColorHover: rgb(var(--v-theme-linkHover));
/* EYE */
.eye {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translateX(-50%) translateY(-50%);
  color: $buttonColorHover;
}
.cardControls:hover .eye {
  color: $buttonColorHover;
}
.cardControls:has(> .tagButton:hover) .eye,
.cardControls:has(> .browserCardMenuIcon:hover) .eye {
  color: $buttonColor;
}

/* BOTTOM CONTROLS */
:deep(.cardControlButton) {
  position: absolute !important;
  bottom: 0px !important;
  color: $buttonColor !important;
}
:deep(.tagButton) {
  left: 0px !important;
}
:deep(.browserCardMenuIcon) {
  right: 0px !important;
}
:deep(.cardControlButton:hover) {
  color: $buttonColorHover !important;
}
</style>
