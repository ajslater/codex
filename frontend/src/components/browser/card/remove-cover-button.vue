<template>
  <ConfirmDialog
    v-if="show"
    :button="false"
    button-text="Remove Cover"
    confirm
    confirm-text="Remove Cover"
    :prepend-icon="mdiImageRemove"
    text="Remove the custom cover from this card?"
    title-text="Remove Cover"
    @confirm="remove"
  />
</template>

<script>
import { mdiImageRemove } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { removeCustomCover } from "@/api/v4/admin";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

const REMOVE_GROUPS = Object.freeze(
  new Set(["publishers", "imprints", "series", "volumes", "arcs", "folders"]),
);

export default {
  name: "RemoveCoverButton",
  components: { ConfirmDialog },
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  emits: ["removed"],
  data() {
    return { mdiImageRemove };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    show() {
      return (
        this.isUserAdmin &&
        REMOVE_GROUPS.has(this.item?.group) &&
        Boolean(this.item?.coverCustomPk) &&
        this.item?.ids?.length > 0
      );
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["bustCoverCache"]),
    ...mapActions(useCommonStore, ["setSessionError"]),
    async remove() {
      try {
        await removeCustomCover({
          group: this.item.group,
          pks: this.item.ids,
        });
        this.bustCoverCache({ ids: this.item.ids, coverCustomPk: null });
        this.$emit("removed");
      } catch (error) {
        console.error("Remove custom cover failed:", error);
        const reason = error?.response?.data?.detail || "Cover removal failed.";
        this.setSessionError(reason);
      }
    },
  },
};
</script>
