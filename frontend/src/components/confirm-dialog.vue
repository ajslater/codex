<template>
  <v-dialog
    v-model="showDialog"
    transition="fab-transition"
    max-width="20em"
    overlay-opacity="0.5"
  >
    <template #activator="{ props }">
      <v-btn v-if="icon" icon v-bind="props">
        <v-icon>{{ icon }}</v-icon>
      </v-btn>
      <v-btn v-else block v-bind="props">
        {{ buttonText }}
      </v-btn>
    </template>
    <div class="confirmDialog">
      <h3>{{ titleText }}</h3>
      {{ objectName }}
      <ConfirmFooter
        :confirm-text="confirmText"
        @confirm="close('confirm')"
        @cancel="close('cancel')"
      />
    </div>
  </v-dialog>
</template>
<script>
import ConfirmFooter from "@/components/confirm-footer.vue";
export default {
  name: "ConfirmDialog",
  components: { ConfirmFooter },
  props: {
    icon: { type: String, default: "" },
    buttonText: { type: String, default: "" },
    titleText: {
      type: String,
      required: true,
    },
    objectName: {
      type: String,
      required: true,
    },
    confirmText: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      showDialog: false,
    };
  },
  methods: {
    close(event) {
      this.$emit(event);
      this.showDialog = false;
    },
  },
};
</script>

<style scoped lang="scss">
.confirmDialog {
  padding: 20px;
  text-align: center;
}
</style>
