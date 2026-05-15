<template>
  <v-dialog
    v-model="show"
    transition="fab-transition"
    min-width="20em"
    width="auto"
    overlay-opacity="0.5"
  >
    <div class="confirmDialog">
      <div class="title">Force Update Tags</div>
      {{ bodyText }}
      <ConfirmFooter
        confirm-text="Force Update Tags"
        @confirm="onConfirm"
        @cancel="onCancel"
      />
    </div>
  </v-dialog>
</template>

<script>
import ConfirmFooter from "@/components/confirm-footer.vue";

export default {
  name: "ForceUpdateConfirmDialog",
  components: { ConfirmFooter },
  props: {
    modelValue: { type: Boolean, default: false },
    affectedCount: { type: Number, required: true },
    subject: { type: String, default: "" },
  },
  emits: ["update:modelValue", "confirm"],
  computed: {
    show: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit("update:modelValue", value);
      },
    },
    bodyText() {
      const noun = this.affectedCount === 1 ? "comic" : "comics";
      const suffix = this.subject ? ` ${this.subject}` : "";
      return `Update tags for ${this.affectedCount} ${noun}${suffix}?`;
    },
  },
  methods: {
    onConfirm() {
      this.show = false;
      this.$emit("confirm");
    },
    onCancel() {
      this.show = false;
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
