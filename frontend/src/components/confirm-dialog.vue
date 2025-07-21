<template>
  <v-dialog
    v-model="showDialog"
    transition="fab-transition"
    min-width="20em"
    width="auto"
    overlay-opacity="0.5"
  >
    <template #activator="{ props }">
      <v-btn
        v-if="button && icon"
        v-bind="props"
        :block="block"
        :density="density"
        :icon="icon"
        :size="size"
        :title="titleText"
        @click="autoConfirm"
      />
      <v-btn
        v-else-if="button"
        v-bind="props"
        :block="block"
        :density="density"
        :size="size"
        :title="titleText"
        @click="autoConfirm"
      >
        <v-icon v-if="prependIcon">{{ prependIcon }}</v-icon>
        {{ buttonText }}
      </v-btn>
      <CodexListItem
        v-else
        v-bind="props"
        :prepend-icon="prependIcon"
        :title="titleText"
        @click="autoConfirm"
      />
    </template>
    <div class="confirmDialog">
      <h3>{{ titleText }}</h3>
      {{ text }}
      <ConfirmFooter
        :confirm-text="confirmText"
        @confirm="close('confirm')"
        @cancel="close('cancel')"
      />
    </div>
  </v-dialog>
</template>
<script>
import CodexListItem from "@/components/codex-list-item.vue";
import ConfirmFooter from "@/components/confirm-footer.vue";
export default {
  name: "ConfirmDialog",
  components: { ConfirmFooter, CodexListItem },
  props: {
    block: {
      type: Boolean,
      default: false,
    },
    button: { type: Boolean, default: true },
    buttonText: { type: String, default: "" },
    confirm: {
      type: Boolean,
      default: true,
    },
    confirmText: {
      type: String,
      required: true,
    },
    density: {
      type: String,
      default: "default",
    },
    icon: { type: String, default: "" },
    prependIcon: { type: String, default: "" },
    size: {
      type: String,
      default: "default",
    },
    text: {
      type: String,
      required: true,
    },
    titleText: {
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
    autoConfirm() {
      if (!this.confirm) {
        this.close("confirm");
      }
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
