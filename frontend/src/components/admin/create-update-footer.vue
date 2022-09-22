<template>
  <footer>
    <div>
      <small v-if="formErrors && formErrors.length > 0" style="color: red">
        <div v-for="error in formErrors" :key="error">
          {{ error }}
        </div>
      </small>
      <small v-else-if="formSuccess" style="color: green">
        {{ formSuccess }}
      </small>
    </div>
    <div>
      <v-btn ref="submit" ripple :disabled="disabled" @click="$emit('submit')">
        {{ modeName }} {{ table }}
      </v-btn>
      <v-btn class="cuCancelButton" ripple @click="$emit('cancel')">
        Cancel
      </v-btn>
    </div>
  </footer>
</template>
<script>
import { mapState } from "pinia";

import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminCreateUpdateFooter",
  props: {
    update: { type: Boolean, default: false },
    table: { type: String, required: true },
    disabled: { type: Boolean, default: false },
  },
  computed: {
    ...mapState(useAdminStore, {
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
    }),
    modeName: function () {
      return this.update ? "Update" : "Add";
    },
  },
};
</script>

<style scoped lang="scss">
.cuCancelButton {
  float: right;
}
</style>
