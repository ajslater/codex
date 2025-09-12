<template>
  <div id="tasks">
    <div>
      <span id="lastTaskLabel">Last Task Queued:</span>
      <span>
        <span v-if="formSuccess" id="success">{{ formSuccess }}</span>
        <span v-else-if="formErrors && formErrors.length > 0" id="error">
          <span v-for="error in formErrors" :key="error">{{ error }}</span>
        </span>
        <span v-else id="noRecentTask">No recent task</span>
      </span>
    </div>
    <div
      v-for="group in tasks"
      :key="group.title"
      fixed-header
      class="taskGroup"
    >
      <h3>
        {{ group.title }}
      </h3>
      <div v-if="!SELECT_GROUPS.includes(group.title)">
        <div
          v-for="item in group.tasks"
          :key="item.value"
          class="trow"
          :class="{ selected: false }"
        >
          <div class="taskBox">
            <ConfirmDialog
              v-if="item.confirm"
              :button-text="item.title"
              :title-text="item.title"
              :text="item.confirm"
              :block="true"
              confirm-text="Confirm"
              @confirm="librarianTask(item.value, item.title)"
            />
            <v-btn
              v-else
              block
              @click="librarianTask(item.value, item.title)"
              :text="item.title"
            />
            <div class="taskDesc">
              {{ item.desc }}
            </div>
          </div>
        </div>
      </div>
      <div v-else class="taskBox">
        <v-select
          :items="group.tasks"
          :model-value="selectValues[group.title]"
          @update:model-value="selectValues[group.title] = $event"
        />
        <v-btn
          block
          @click="
            librarianTask(
              selectValues[group.title],
              selectAttr(group.title, 'title'),
            )
          "
          :text="selectAttr(group.title, 'title')"
        />
        <div class="taskDesc">
          {{ selectAttr(group.title, "desc") }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { tasks } from "@/choices/admin-tasks.json";
import ConfirmDialog from "@/components/confirm-dialog.vue";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";

const SELECT_GROUPS = ["Notify"];
Object.freeze(SELECT_GROUPS);

export default {
  name: "AdminTasksTab",
  components: {
    ConfirmDialog,
  },
  data() {
    return {
      SELECT_GROUPS,
      selectValues: {
        Notify: "notify_library_changed",
      },
      tasks,
    };
  },
  computed: {
    ...mapState(useCommonStore, {
      formSuccess: (state) => state.form.success,
      formErrors: (state) => state.form.errors,
    }),
    selectMaps() {
      // Construct a value keyed map from the vuetified task list.
      const maps = {};
      for (const group of tasks) {
        if (SELECT_GROUPS.includes(group.title)) {
          maps[group.title] = {};
          for (const item of group.tasks) {
            maps[group.title][item.value] = item;
          }
        }
      }
      return maps;
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["librarianTask"]),
    selectAttr(title, attr) {
      // Get the attribute from the map lookup
      const value = this.selectValues[title];
      return this.selectMaps[title][value][attr];
    },
  },
};
</script>

<style scoped lang="scss">
#lastTaskLabel {
  margin-right: 1em;
}

#success {
  color: rgb(var(--v-theme-success));
}

#error {
  color: rgb(var(--v-theme-error));
}

#noRecentTask {
  color: rgb(var(--v-theme-textDisabled));
}

.taskGroup {
  margin-top: 1em;
}

.taskBox {
  padding: 12px;
  margin: 10px;
  border-radius: 5px;
  background-color: rgb(var(--v-theme-surface-light));
}

.taskDesc {
  vertical-align: top;
  color: rgb(var(--v-theme-textSecondary));
  padding-top: 0.25em;
}

#tasks {
  max-width: 512px;
  margin-left: auto;
  margin-right: auto;
}
</style>
