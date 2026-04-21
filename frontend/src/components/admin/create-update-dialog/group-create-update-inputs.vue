<template>
  <div>
    <v-text-field
      v-model="row.name"
      label="Group Name"
      :rules="rules.name"
      clearable
      autofocus
    />
    <v-radio-group
      inline
      label="Type"
      :model-value="row.exclude"
      hide-details="auto"
      @update:model-value="row.exclude = $event"
    >
      <v-radio :value="false">
        <template #label>
          <GroupChip
            :item="{ name: 'Include', exclude: false }"
            title-key="name"
            group-type
          />
        </template>
      </v-radio>
      <v-radio :value="true">
        <template #label>
          <GroupChip
            :item="{ name: 'Exclude', exclude: true }"
            title-key="name"
            group-type
          />
        </template>
      </v-radio>
    </v-radio-group>
    <AdminRelationPicker
      :model-value="row.userSet"
      label="Users"
      :objs="users"
      title-key="username"
      @update:model-value="row.userSet = $event"
    />
    <AdminRelationPicker
      :model-value="row.librarySet"
      label="Libraries"
      :objs="normalLibraries"
      title-key="path"
      @update:model-value="row.librarySet = $event"
    />
    <v-select
      :model-value="row.ageRatingMetron"
      :items="ageRatingChoices"
      label="Age Restriction"
      clearable
      hide-details="auto"
      placeholder="Any"
      @update:model-value="row.ageRatingMetron = $event"
    />
  </div>
</template>

<script>
import { mapState } from "pinia";

import METRON_AGE_RATING_CHOICES from "@/choices/metron-age-rating-choices.json";
import AdminRelationPicker from "@/components/admin/create-update-dialog/relation-picker.vue";
import createUpdateInputsMixin from "@/components/admin/create-update-dialog/create-update-inputs-mixin.js";
import GroupChip from "@/components/admin/group-chip.vue";
import { useAdminStore } from "@/stores/admin";

const UPDATE_KEYS = Object.freeze([
  "name",
  "userSet",
  "librarySet",
  "exclude",
  "ageRatingMetron",
]);
const EMPTY_ROW = Object.freeze({
  name: "",
  userSet: [],
  librarySet: [],
  exclude: false,
  ageRatingMetron: null,
});

export default {
  name: "AdminGroupCreateUpdateInputs",
  components: {
    AdminRelationPicker,
    GroupChip,
  },
  mixins: [createUpdateInputsMixin],
  data() {
    return {
      rules: {
        name: [
          (v) => !!v || "Name is required",
          (v) => (!!v && !this.names.has(v.trim())) || "Name already used",
        ],
      },
    };
  },
  computed: {
    ...mapState(useAdminStore, ["normalLibraries"]),
    ...mapState(useAdminStore, {
      groups: (state) => state.groups,
      users: (state) => state.users,
    }),
    names() {
      return this.nameSet(this.groups, "name", this.oldRow, true);
    },
    ageRatingChoices() {
      return METRON_AGE_RATING_CHOICES.METRON_AGE_RATING;
    },
  },
  UPDATE_KEYS,
  EMPTY_ROW,
};
</script>
