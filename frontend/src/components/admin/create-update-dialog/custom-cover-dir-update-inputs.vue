<template>
  <v-checkbox
    v-model="row.events"
    hide-details="auto"
    hint="Update Codex instantly when the filesystem changes"
    label="Watch Filesystem Events"
    :persistent-hint="true"
  />
  <v-checkbox
    v-model="row.poll"
    label="Poll Filesystem Periodically"
    hide-details="auto"
    hint="Periodically poll the custom-covers dir for changes"
    :persistent-hint="true"
  />
  <TimeTextField
    v-model="row.pollEvery"
    label="Poll Every"
    :disabled="!row.poll"
  />
</template>

<script>
import _ from "lodash";
import { mapActions } from "pinia";

import TimeTextField from "@/components/admin/create-update-dialog/time-text-field.vue";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = ["events", "poll", "pollEvery"];
Object.freeze(UPDATE_KEYS);
const EMPTY_ROW = {
  events: true,
  poll: true,
  pollEvery: "01:00:00",
};
Object.freeze(EMPTY_ROW);

export default {
  // eslint-disable-next-line no-secrets/no-secrets
  name: "AdminCustomCoverDirUpdateInputs",
  components: {
    TimeTextField,
  },
  props: {
    oldRow: {
      type: [Object, Boolean],
      default: false,
    },
  },
  emits: ["change"],
  data() {
    return {
      rules: {},
      row: _.cloneDeep(this.oldRow || EMPTY_ROW),
    };
  },
  watch: {
    row: {
      handler(to) {
        this.$emit("change", to);
      },
      deep: true,
    },
    oldRow: {
      handler(to) {
        this.row = _.cloneDeep(to);
      },
      deep: true,
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["nameSet"]),
  },
  UPDATE_KEYS,
  EMPTY_ROW,
};
</script>
