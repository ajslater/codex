<template>
  <v-select
    chips
    deletable-chips
    density="compact"
    :multiple="true"
    small-chips
    v-bind="$attrs"
  />
</template>

<script>
export default {
  name: "AdminRelationPicker",
};
</script>
