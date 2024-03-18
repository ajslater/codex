<template>
  <v-select
    :chips="true"
    :closable-chips="true"
    density="compact"
    :multiple="true"
    :items="vuetifyItems"
    v-bind="$attrs"
  >
    <template #chip="{ item }">
      <GroupChip title-key="title" :item="item" :group-type="groupType" />
    </template>
  </v-select>
</template>

<script>
import GroupChip from "@/components/admin/group-chip.vue";

export default {
  name: "AdminRelationPicker",
  components: { GroupChip },
  props: {
    objs: {
      type: Object,
      required: true,
    },
    titleKey: {
      type: String,
      required: true,
    },
    groupType: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    vuetifyItems() {
      const result = [];
      for (const obj of this.objs) {
        result.push({ ...obj, value: obj.pk, title: obj[this.titleKey] });
      }
      return result;
    },
  },
};
</script>
