<template>
  <v-select
    chips
    deletable-chips
    dense
    :multiple="true"
    small-chips
    v-bind="$attrs"
    v-on="$listeners"
  />
</template>

<script>
export default {
  name: "AdminRelationPicker",
};
</script>
