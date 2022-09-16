<template>
  <v-simple-table fixed-header class="taskTable">
    <tbody>
      <tr class="trow">
        <td>Last Task Queued</td>
        <td>
          <span v-if="formSuccess" id="success">{{ formSuccess }}</span>
          <span v-else-if="formErrors && formErrors.length > 0" id="error">
            <span v-for="error in formErrors" :key="error">{{ error }}</span>
          </span>
          <span v-else id="noRecentTask">No recent task</span>
        </td>
      </tr>
    </tbody>
    <tbody v-for="group in tasks" :key="group.title">
      <tr class="trow">
        <td class="title" colspan="2">{{ group.title }}</td>
      </tr>
      <tr v-for="item in group.tasks" :key="item.value" class="trow">
        <td class="tcol">
          <AdminTaskConfirmDialog
            v-if="item.confirm"
            :task="item"
            @confirmed="queueTask(item)"
          />
          <v-btn v-else block ripple @click="queueTask(item)">{{
            item.text
          }}</v-btn>
        </td>
        <td class="tcolG desc">{{ item.desc }}</td>
      </tr>
    </tbody>
  </v-simple-table>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { tasks } from "@/choices-admin.json";
import AdminTaskConfirmDialog from "@/components/admin/task-dialog.vue";
import { useAdminStore } from "@/stores/admin";

export default {
  name: "AdminTasksPanel",
  components: {
    AdminTaskConfirmDialog,
  },
  data() {
    return {
      tasks,
    };
  },
  computed: {
    ...mapState(useAdminStore, {
      formSuccess: (state) => state.form.success,
      formErrors: (state) => state.form.errors,
    }),
  },
  methods: {
    ...mapActions(useAdminStore, ["librarianTask"]),
    queueTask(item) {
      if (item.confirm) {
        console.log("launch dialog");
      }
      this.librarianTask(item.value, item.text);
    },
  },
};
</script>

<style scoped lang="scss">
#success {
  color: green;
}
#error {
  color: red;
}
#noRecentTask {
  color: gray;
}
.title {
  font-weight: bold;
  font-size: larger;
}
.trow {
  border: none;
}
.tcol {
  border: none;
}
.desc {
  vertical-align: top;
  color: lightgrey;
  min-width: 15em;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
.taskTable > div > table {
  border: none;
  border-collapse: collapse;
}
</style>
