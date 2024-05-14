<template>
  <ScaleButton variant="plain" class="toolbarButton">
    <template v-for="(props, name) in $slots" #[name]="slotData">
      <slot :name="name" :props="props" v-bind="slotData" />
    </template>
  </ScaleButton>
</template>
<script>
import ScaleButton from "@/components/scale-button.vue";
export default {
  name: "ToolbarButton",
  components: {
    ScaleButton,
  },
};
</script>
<style scoped lang="scss">
.toolbarButton {
  padding-bottom: 7px;
}
</style>
