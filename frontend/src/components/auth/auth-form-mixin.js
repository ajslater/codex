/**
 * Mixin for auth form dialogs: login, change-password.
 *
 * Provides:
 *   - data.submitButtonEnabled
 *   - Deep watcher on `credentials` that auto-validates via $refs.form
 *   - Computed: formErrors, formSuccess from commonStore
 *
 * Using components require:
 *   - data.credentials  (their own shape)
 *   - data.rules
 *   - A <v-form ref="form"> in their template
 */
import { mapState } from "pinia";

import { useCommonStore } from "@/stores/common";

export default {
  data() {
    return {
      submitButtonEnabled: false,
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
      formSuccess: (state) => state.form.success,
    }),
  },
  watch: {
    credentials: {
      handler() {
        const form = this.$refs.form;
        if (!form) {
          this.submitButtonEnabled = false;
          return;
        }
        form
          .validate()
          .then(({ valid }) => {
            this.submitButtonEnabled = valid;
            return this.submitButtonEnabled;
          })
          .catch(() => {
            this.submitButtonEnabled = false;
          });
      },
      deep: true,
    },
  },
};
