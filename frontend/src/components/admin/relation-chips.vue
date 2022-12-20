<template>
  <span>
    <v-chip v-for="pk in pks" :key="pk" size="small">
      {{ map[pk] }}
    </v-chip>
  </span>
</template>
<script>
export default {
  name: "RelationChips",
  props: {
    pks: {
      type: Array,
      required: true,
    },
    map: {
      type: Object,
      required: true,
    },
  },
};
</script>
<style scoped lang="scss"></style>
