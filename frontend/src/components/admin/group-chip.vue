<template>
  <v-chip
    :class="{
      include: groupType && !item.exclude,
      exclude: groupType && item.exclude,
    }"
    :text="item[titleKey]"
    :value="item.value"
  />
</template>
<script>
export default {
  name: "GroupChip",
  props: {
    titleKey: {
      type: String,
      required: true,
    },
    groupType: {
      type: Boolean,
      default: false,
    },
    item: {
      type: Object,
      required: true,
    },
  },
};
</script>
<style scoped lang="scss">
.include {
  background-color: rgb(var(--v-theme-includeGroup));
}
.exclude{
  background-color: rgb(var(--v-theme-excludeGroup));
}
</style>
