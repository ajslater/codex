<template>
  <div v-if="show">
    <CodexListItem
      class="listItem"
      :prepend-icon="mdiImagePlus"
      :title="label"
      @click="pickFile"
    />
    <input
      ref="fileInput"
      accept="image/*"
      class="hiddenInput"
      type="file"
      @change="onFile"
    />
  </div>
</template>

<script>
import { mdiImagePlus } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { uploadCustomCover } from "@/api/v3/admin";
import CodexListItem from "@/components/codex-list-item.vue";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

const UPLOAD_GROUPS = Object.freeze(new Set(["p", "i", "s", "v", "a", "f"]));

export default {
  name: "UploadCoverButton",
  components: { CodexListItem },
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  emits: ["uploaded"],
  data() {
    return { mdiImagePlus };
  },
  computed: {
    ...mapState(useAuthStore, ["isUserAdmin"]),
    show() {
      return (
        this.isUserAdmin &&
        UPLOAD_GROUPS.has(this.item?.group) &&
        this.item?.ids?.length > 0 &&
        !this.item.ids.includes(0)
      );
    },
    label() {
      return this.item?.coverCustomPk ? "Replace Cover" : "Upload Cover";
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["bustCoverCache"]),
    ...mapActions(useCommonStore, ["setSessionError"]),
    pickFile() {
      this.$refs.fileInput?.click();
    },
    async onFile(event) {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (!file) return;
      try {
        const response = await uploadCustomCover({
          group: this.item.group,
          pks: this.item.ids,
          file,
        });
        const pk = response?.data?.customCoverPk;
        if (pk) {
          this.bustCoverCache({ ids: this.item.ids, coverCustomPk: pk });
        }
        this.$emit("uploaded", pk);
      } catch (error) {
        console.error("Upload custom cover failed:", error);
        const reason = error?.response?.data?.detail || "Cover upload failed.";
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
</style>
