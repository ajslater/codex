<template>
  <v-dialog
    v-model="showDialog"
    transition="fab-transition"
    max-width="20em"
    overlay-opacity="0.5"
    class="confirmMarkReadDialog"
  >
    <template #activator="{ on }">
      <v-list-item ripple v-on="on">
        <v-list-item-content>
          <v-list-item-title>{{ text }}</v-list-item-title>
        </v-list-item-content>
      </v-list-item>
    </template>
    <div id="confirmMarkReadDialog">
      <h3>
        {{ name }}
      </h3>
      {{ text }}
      <ConfirmFooter
        confirm-text="Confirm"
        @confirm="click('confirm')"
        @cancel="click('cancel')"
      />
    </div>
  </v-dialog>
</template>

<script>
import { mdiTrashCan } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ConfirmFooter from "@/components/confirm-footer.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "ConfirmMarkReadDialog",
  components: {
    ConfirmFooter,
  },
  props: {
    text: {
      type: String,
      required: true,
    },
    name: {
      type: String,
      default: "",
    },
  },
  emits: ["confirm", "cancel"],
  data() {
    return {
      showDialog: false,
      mdiTrashCan,
    };
  },
  computed: {
    ...mapState(useAdminStore, {}),
  },
  methods: {
    ...mapActions(useAdminStore, ["deleteRow"]),
    click(event) {
      this.$emit(event);
      this.showDialog = false;
    },
  },
};
</script>

<style scoped lang="scss">
#confirmMarkReadDialog {
  padding: 20px;
  text-align: center;
}
</style>
