<template>
  <div class="cardControls">
    <v-icon v-if="item.group === 'c'" class="eye">
      {{ eyeIcon }}
    </v-icon>
    <span class="cardControlButton">
      <MetadataButton
        :group="item.group"
        :pk="item.pk"
        :children="item.childCount"
      />
      <BrowserCardMenu
        :group="item.group"
        :pk="item.pk"
        :finished="item.finished"
      />
    </span>
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
@import "vuetify/src/styles/styles.sass";
@import "../../book-cover.scss";
.cardControls {
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
#browsePaneContainer .tagIcon {
  position: absolute !important;
  left: $button-margin !important;
  bottom: $button-margin !important;
}
#browsePaneContainer .browserCardMenuIcon {
  position: absolute !important;
  right: $button-margin !important;
  bottom: $button-margin !important;
}

$browser-card-icon-size: 24px;
$unselected-icon-color: #a0a0a0;
#browsePaneContainer .cardControlButton .v-icon {
  color: $unselected-icon-color !important;
  width: $browser-card-icon-size;
  height: $browser-card-icon-size;
}
#browsePaneContainer .cardControlButton .v-icon:hover {
  color: white !important;
}

#browsePaneContainer .cardControls:has(> .cardControlButton:hover) .eye {
  /* this selector only works on safari 2022-08 */
  color: $unselected-icon-color;
}

@import "vuetify/src/styles/styles.sass";
@media #{map-get($display-breakpoints, 'sm-and-down')} {
  $small-button-margin: 5px;
  #browsePaneContainer .tagIcon {
    left: $small-button-margin !important;
    bottom: $small-button-margin !important;
  }
  #browsePaneContainer .browserCardMenuIcon {
    right: $small-button-margin !important;
    bottom: $small-button-margin !important;
  }
}
</style>
