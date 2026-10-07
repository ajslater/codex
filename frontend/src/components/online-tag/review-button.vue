<!--
  Opens the online-tagging Match Review dialog while matches wait for an
  admin. The dialog never opens on its own, so this button is the cue in the
  browser and reader top toolbars and the admin title bar; the settings drawer
  item is the second path. Phones show the icon and count only.

  A plain v-btn, not ScaleButton: compact density on phones stacks with
  size="small" and shrinks the button to 16px tall.
-->
<template>
  <v-btn
    v-if="show"
    class="reviewButton"
    size="small"
    variant="tonal"
    color="warning"
    :prepend-icon="mdiTagMultiple"
    :title="label"
    :aria-label="label"
    @click="onClick"
  >
    <span class="d-none d-sm-inline">Review&nbsp;</span>{{ countText }}
  </v-btn>
</template>

<script>
import { mdiTagMultiple } from "@mdi/js";
import { mapState, mapWritableState } from "pinia";

import { NUMBER_FORMAT } from "@/datetime";
import { useAuthStore } from "@/stores/auth";
import { useOnlineTagStore } from "@/stores/online-tag";

export default {
  name: "OnlineTagReviewButton",
  data() {
    return {
      mdiTagMultiple,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    ...mapState(useOnlineTagStore, ["pendingComicCount"]),
    ...mapWritableState(useOnlineTagStore, ["promptDialogOpen"]),
    show() {
      return Boolean(this.isUserAdmin) && this.pendingComicCount > 0;
    },
    countText() {
      return NUMBER_FORMAT.format(this.pendingComicCount);
    },
    label() {
      const count = this.pendingComicCount;
      return `Review ${this.countText} online tagging match${count === 1 ? "" : "es"}`;
    },
  },
  methods: {
    onClick() {
      // The OnlineTagPromptPopup (mounted in browser.vue, admin.vue and
      // reader.vue) watches this flag.
      this.promptDialogOpen = true;
    },
  },
};
</script>

<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  .reviewButton {
    margin-right: 8px;
  }
}
</style>
