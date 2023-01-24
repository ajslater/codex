<template>
  <footer>
    <div>
      <small v-if="errors && errors.length > 0" class="errors">
        <div v-for="(error, index) in errors" :key="index">
          {{ error }}
        </div>
      </small>
      <small v-else-if="success" class="success">
        {{ success }}
      </small>
      <small v-else>&nbsp;</small>
    </div>
    <ConfirmFooter
      :confirm-text="`${verb} ${table}`"
      :disabled="disabled"
      @confirm="$emit('submit')"
      @cancel="$emit('cancel')"
    />
  </footer>
</template>
<script>
import { mapActions, mapState } from "pinia";

import ConfirmFooter from "@/components/confirm-footer.vue";
import { useCommonStore } from "@/stores/common";

export default {
  name: "SubmitFooter",
  components: {
    ConfirmFooter,
  },
  props: {
    verb: { type: String, required: true },
    table: { type: String, required: true },
    disabled: { type: Boolean, default: false },
  },
  emits: ["cancel", "submit"],
  computed: {
    ...mapState(useCommonStore, {
      errors: (state) => state.form.errors,
      success: (state) => state.form.success,
    }),
  },
  beforeMount() {
    this.clearErrors();
  },
  methods: {
    ...mapActions(useCommonStore, ["clearErrors"]),
  },
};
</script>

<style scoped lang="scss">
.errors {
  color: rgb(var(--v-theme-error));
}
.success {
  color: rgb(var(--v-theme-success));
}
</style>
