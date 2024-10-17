<template>
  <v-dialog
    v-model="showDialog"
    transition="fab-transition"
    max-width="20em"
    overlay-opacity="0.5"
  >
    <template #activator="{ props }">
      <v-btn
        v-if="button && icon"
        v-bind="props"
        :block="block"
        :icon="icon"
        :size="size"
        :density="density"
        :title="titleText"
      />
      <v-btn v-else-if="button" v-bind="props" :block="block">
        <v-icon v-if="prependIcon">{{ prependIcon }}</v-icon>
        {{ buttonText }}
      </v-btn>
      <CodexListItem
        v-else
        v-bind="props"
        :prepend-icon="prependIcon"
        :title="titleText"
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
    button: { type: Boolean, default: true },
    icon: { type: String, default: "" },
    prependIcon: { type: String, default: "" },
    buttonText: { type: String, default: "" },
    titleText: {
      type: String,
      required: true,
    },
    block: {
      type: Boolean,
      default: false,
    },
    text: {
      type: String,
      required: true,
    },
    confirmText: {
      type: String,
      required: true,
    },
    size: {
      type: String,
      default: "default",
    },
    density: {
      type: String,
      default: "default",
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
