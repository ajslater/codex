<template>
  <v-dialog
    v-model="showDialog"
    transition="fab-transition"
    max-width="20em"
    overlay-opacity="0.5"
  >
    <template #activator="{ on }">
      <v-btn v-if="task.icon" icon ripple v-on="on">
        <v-icon>{{ mdiDatabaseImportOutline }}</v-icon>
      </v-btn>
      <v-btn v-else block ripple v-on="on">
        {{ task.text }}
      </v-btn>
    </template>
    <div id="taskConfirmDialog">
      <h2>{{ task.text }}</h2>
      {{ task.confirm }}
      <footer id="buttonFooter">
        <v-btn id="confirmButton" ripple @click="confirm"> Confirm </v-btn>
        <CancelButton @click="showDialog = false" />
      </footer>
    </div>
  </v-dialog>
</template>

<script>
import { mdiDatabaseImportOutline } from "@mdi/js";

import CancelButton from "@/components/cancel-button.vue";

export default {
  name: "AdminTaskConfirmDialog",
  components: {
    CancelButton,
  },
  props: {
    task: {
      type: Object,
      required: true,
    },
  },
  emits: ["confirmed"],
  data() {
    return {
      showDialog: false,
      mdiDatabaseImportOutline,
    };
  },
  methods: {
    confirm: function () {
      this.$emit("confirmed");
      this.showDialog = false;
    },
  },
};
</script>

<style scoped lang="scss">
#taskConfirmDialog {
  padding: 20px;
  text-align: center;
  background-color: #272727;
}
#buttonFooter {
  margin-top: 1em;
  text-align: left;
}
</style>
