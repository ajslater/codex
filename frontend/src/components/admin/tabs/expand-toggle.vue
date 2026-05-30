<!--
  A chevron + label disclosure button used to expand sub-status and log panels.
  `v-model` holds the expanded state. Unifies the two hand-written copies of the
  old .expandToggle block. See DESIGN.md §4.
-->
<template>
  <button
    type="button"
    class="adminExpandToggle"
    @click="$emit('update:modelValue', !modelValue)"
  >
    <v-icon size="small">
      {{ modelValue ? mdiChevronUp : mdiChevronDown }}
    </v-icon>
    <span class="adminExpandLabel">
      <slot>{{ label }}</slot>
    </span>
  </button>
</template>

<script>
import { mdiChevronDown, mdiChevronUp } from "@mdi/js";

export default {
  name: "AdminExpandToggle",
  props: {
    modelValue: { type: Boolean, default: false },
    label: { type: String, default: "" },
  },
  emits: ["update:modelValue"],
  data() {
    return {
      mdiChevronDown,
      mdiChevronUp,
    };
  },
};
</script>

<style scoped lang="scss">
@use "@/components/admin/tabs/admin-section.scss";

.adminExpandLabel {
  user-select: none;
}
</style>
