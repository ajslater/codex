<!--
  The Save / Revert row at the foot of a settings form. The primary button is
  type="submit" so it triggers the enclosing <v-form @submit.prevent>; the
  secondary button emits `revert`. Unifies the four hand-written copies of the
  old .settingsActions block. See DESIGN.md §6.
-->
<template>
  <div class="adminActionBar">
    <v-btn
      type="submit"
      variant="tonal"
      size="small"
      :loading="saving"
      :disabled="saveDisabled"
    >
      {{ saveText }}
    </v-btn>
    <v-btn
      variant="text"
      size="small"
      :disabled="revertDisabled"
      @click="$emit('revert')"
    >
      {{ revertText }}
    </v-btn>
  </div>
</template>

<script>
export default {
  name: "AdminActionBar",
  props: {
    saveText: { type: String, default: "Save" },
    revertText: { type: String, default: "Revert" },
    saving: { type: Boolean, default: false },
    saveDisabled: { type: Boolean, default: false },
    revertDisabled: { type: Boolean, default: false },
  },
  emits: ["revert"],
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";
</style>
