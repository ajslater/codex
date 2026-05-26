<template>
  <span class="replaceCover">
    <v-btn
      :density="density"
      :icon="mdiPencil"
      :size="size"
      title="Replace Cover"
      @click="pickFile"
    />
    <input
      ref="fileInput"
      accept="image/*"
      class="hiddenInput"
      type="file"
      @change="onFile"
    />
  </span>
</template>

<script>
import { mdiPencil } from "@mdi/js";
import { mapActions } from "pinia";

import { uploadCustomCover } from "@/api/v3/admin";
import { useAdminStore } from "@/stores/admin";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

export default {
  name: "ReplaceCoverButton",
  props: {
    density: { type: String, default: "compact" },
    item: { type: Object, required: true },
    size: { type: String, default: "small" },
  },
  data() {
    return { mdiPencil };
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTable"]),
    ...mapActions(useBrowserStore, ["bustCoverCache"]),
    ...mapActions(useCommonStore, ["setSessionError"]),
    pickFile() {
      this.$refs.fileInput?.click();
    },
    async onFile(event) {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (!file || !this.item?.linkedGroupPk) return;
      try {
        const response = await uploadCustomCover({
          group: this.item.group,
          pks: [this.item.linkedGroupPk],
          file,
        });
        const pk = response?.data?.customCoverPk;
        // The upload creates a new CustomCover row and GCs this one,
        // so refresh the table to swap them out.
        this.loadTable("CustomCover", { force: true });
        // Bust any browser cards still rendering the replaced cover.
        this.bustCoverCache({
          ids: [this.item.linkedGroupPk],
          coverCustomPk: pk,
        });
      } catch (error) {
        console.error("Replace custom cover failed:", error);
        const reason = error?.response?.data?.detail || "Cover replace failed.";
        this.setSessionError(reason);
      }
    },
  },
};
</script>

<style scoped lang="scss">
.hiddenInput {
  display: none;
}

.replaceCover :deep(> button) {
  opacity: 0.7;
}

.replaceCover :deep(> button:hover) {
  opacity: 1;
}
</style>
