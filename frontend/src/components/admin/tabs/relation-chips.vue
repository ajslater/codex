<template>
  <span>
    <GroupChip
      v-for="pk in pks"
      :key="pk"
      :title-key="titleKey"
      :group-type="groupType"
      :item="map[pk]"
    />
  </span>
</template>
<script>
import GroupChip from "@/components/admin/group-chip.vue";
export default {
  name: "RelationChips",
  components: {
    GroupChip,
  },
  props: {
    pks: {
      type: Array,
      required: true,
    },
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
    map() {
      const result = {};
      for (const obj of this.objs) {
        result[obj.pk] = obj;
      }
      return result;
    },
  },
};
</script>
