<template>
  <footer class="confirmFooter">
    <v-btn
      class="confirmButton"
      :disabled="disabled"
      @click="$emit('confirm')"
      >{{ confirmText }}</v-btn
    >

    <v-btn class="cancelButton" @click="$emit('cancel')">Cancel</v-btn>
  </footer>
</template>
<script>
export default {
  name: "ConfirmFooter",
  props: {
    confirmText: { type: String, required: true },
    disabled: { type: Boolean, default: false },
  },
  emits: ["confirm", "cancel"],
};
</script>

<style scoped lang="scss">
.confirmFooter {
  display: flex;
  justify-content: space-between;
  margin: auto;
  margin-top: 1em;
}
</style>
