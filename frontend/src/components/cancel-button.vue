<template>
  <v-btn class="cancelButton" v-bind="$attrs">Cancel</v-btn>
</template>
<script>
export default {
  name: "CancelButton",
};
</script>

<style scoped lang="scss">
.cancelButton {
  float: right;
}
</style>
