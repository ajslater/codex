<template>
  <ConfirmDialog
    v-if="show"
    :block="block"
    :button="button"
    :button-text="actionText"
    :confirm="needsConfirm"
    confirm-text="Force Update Tags"
    :density="density"
    :prepend-icon="mdiAutorenew"
    :size="size"
    :text="bodyText"
    :title-text="actionText"
    @confirm="forceUpdate"
  />
</template>

<script>
import { mdiAutorenew } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

const CHILD_WARNING_LIMIT = 99;

export default {
  name: "ForceUpdateButton",
  components: { ConfirmDialog },
  props: {
    block: {
      type: Boolean,
      default: false,
    },
    button: {
      type: Boolean,
      default: false,
    },
    density: {
      type: String,
      default: "default",
    },
    item: {
      type: Object,
      required: true,
    },
    size: {
      type: String,
      default: "default",
    },
  },
  data() {
    return { mdiAutorenew };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    ...mapState(useBrowserStore, ["groupNames"]),
    affectedCount() {
      if (this.item.group === "comics") {
        return this.item.ids?.length || 0;
      }
      return this.item.childCount || 0;
    },
    show() {
      return (
        this.isUserAdmin &&
        this.item?.ids?.length > 0 &&
        !this.item.ids.includes(0)
      );
    },
    needsConfirm() {
      return this.affectedCount > CHILD_WARNING_LIMIT;
    },
    actionText() {
      const words = ["Force Update Tags for"];
      if (this.item.group !== "comics") {
        words.push("Entire");
      }
      const groupName = this.groupNames[this.item.group];
      if (groupName) {
        words.push(groupName);
      }
      return words.join(" ");
    },
    bodyText() {
      const noun = this.affectedCount === 1 ? "comic" : "comics";
      const name = this.item.name;
      const suffix = name ? ` in ${name}` : "";
      return `Update tags for ${this.affectedCount} ${noun}${suffix}?`;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["forceUpdateGroup"]),
    forceUpdate() {
      this.forceUpdateGroup({ group: this.item.group, ids: this.item.ids });
    },
  },
};
</script>

<style scoped lang="scss">
:deep(.v-icon) {
  color: rgb(var(--v-theme-textDisabled));
}
</style>
