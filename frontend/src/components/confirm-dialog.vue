<template>
  <v-dialog
    v-model="showDialog"
    transition="fab-transition"
    min-width="320"
    width="auto"
    overlay-opacity="0.5"
  >
    <template v-if="!controlled" #activator="{ props }">
      <v-btn
        v-if="button && icon"
        v-bind="props"
        :block="block"
        :density="density"
        :icon="icon"
        :size="size"
        :title="titleText"
        :variant="variant || undefined"
        @click="autoConfirm"
      />
      <v-btn
        v-else-if="button"
        v-bind="props"
        :block="block"
        :color="color || undefined"
        :density="density"
        :size="size"
        :title="titleText"
        :variant="variant || undefined"
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
      <div class="title">{{ titleText }}</div>
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
    color: { type: String, default: "" },
    confirmText: {
      type: String,
      required: true,
    },
    density: {
      type: String,
      default: "default",
    },
    icon: { type: String, default: "" },
    /*
     * Set it to open and close the dialog from outside, as for a dialog
     * launched from a menu; it then renders no activator of its own. Left
     * null, the dialog opens from its own button. Null, not false, is the
     * default, because Vue casts an absent Boolean prop to false.
     */
    modelValue: { type: Boolean, default: null },
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
    variant: { type: String, default: "" },
  },
  emits: ["cancel", "confirm", "update:modelValue"],
  data() {
    return {
      open: false,
    };
  },
  computed: {
    controlled() {
      return this.modelValue !== null;
    },
    showDialog: {
      get() {
        return this.controlled ? this.modelValue : this.open;
      },
      set(value) {
        // Every close reports here, a scrim click or Escape included.
        this.open = value;
        this.$emit("update:modelValue", value);
      },
    },
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

.title {
  padding-bottom: 10px;
  font-weight: bolder;
  font-size: larger;
}
</style>
