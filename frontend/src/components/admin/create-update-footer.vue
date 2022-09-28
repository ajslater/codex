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
      <CancelButton @click="$emit('cancel')" />
    </div>
  </footer>
</template>
<script>
import { mapState } from "pinia";

import CancelButton from "@/components/cancel-button.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminCreateUpdateFooter",
  components: {
    CancelButton,
  },
  props: {
    update: { type: Boolean, default: false },
    table: { type: String, required: true },
    disabled: { type: Boolean, default: false },
  },
  emits: ["cancel"],
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
