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
        <v-btn class="cancelButton" ripple @click="showDialog = false">
          Cancel
        </v-btn>
      </footer>
    </div>
  </v-dialog>
</template>

<script>
import { mdiDatabaseImportOutline } from "@mdi/js";

export default {
  name: "AdminTaskConfirmDialog",
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
.cancelButton {
  float: right;
}
</style>
