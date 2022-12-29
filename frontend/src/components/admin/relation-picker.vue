<template>
  <v-select
    :chips="true"
    :closable-chips="true"
    density="compact"
    :multiple="true"
    v-bind="$attrs"
  />
</template>

<script>
export default {
  name: "AdminRelationPicker",
};
</script>
