<template>
  <v-btn class="cancelButton" ripple v-bind="$attrs" v-on="$listeners"
    >Cancel</v-btn
  >
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
