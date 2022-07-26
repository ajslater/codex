<template>
  <v-expand-transition>
    <div v-if="librarianStatuses.length > 0">
      <v-divider />
      <h4>Librarian Tasks</h4>
      <v-expand-transition
        v-for="status of librarianStatuses"
        :key="`${status.type} ${status.name}`"
      >
        <div nav class="statusItem">
          <div class="statusItemTitle">
            {{ status.type }} {{ status.name }}
            <span v-if="status.total">
              {{ status.complete }}/{{ status.total }}
            </span>
          </div>
          <v-progress-linear
            color="#cc7b19"
            :indeterminate="status.total == null"
            :value="(100 * +status.complete) / +status.total"
            bottom
          />
        </div>
      </v-expand-transition>
    </div>
  </v-expand-transition>
</template>

<script>
import { mapActions, mapState } from "vuex";

export default {
  name: "AdminStatusList",
  computed: {
    ...mapState("admin", {
      librarianStatuses: (state) => state.librarianStatuses,
    }),
  },
  mounted() {
    // this.fetchLibrarianStatuses();
  },
  methods: {
    ...mapActions("admin", ["fetchLibrarianStatuses"]),
  },
};
</script>

<style scoped lang="scss">
h4 {
  padding-top: 10px;
  padding-left: 16px;
  padding-right: 10px;
}
.statusItem {
  padding-left: 16px;
  padding-right: 5px;
  padding-bottom: 10px;
  color: gray;
}
</style>
