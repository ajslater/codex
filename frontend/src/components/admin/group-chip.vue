<template>
  <v-chip :class="classes" :text="text" :value="value" />
</template>
<script>
export default {
  name: "GroupChip",
  props: {
    titleKey: {
      type: String,
      default: "",
    },
    groupType: {
      type: Boolean,
      default: undefined,
    },
    item: {
      type: Object,
      default: undefined,
    },
  },
  computed: {
    classes() {
      let cls = {};
      if (this.groupType && this.item) {
        cls.include = !this.item.exclude;
        cls.exclude = this.item.exclude;
      }
      return cls;
    },
    text() {
      if (this.item && this.titleKey) {
        return this.item[this.titleKey];
      }
      return "";
    },
    value() {
      if (!this.item) {
        return;
      }
      return this.groupType ? this.item.exclude : this.item.value;
    },
  },
};
</script>
<style scoped lang="scss">
.include {
  background-color: rgb(var(--v-theme-includeGroup));
}

.exclude {
  background-color: rgb(var(--v-theme-excludeGroup));
}
</style>
