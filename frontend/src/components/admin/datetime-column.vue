<template>
  <div v-if="dttm">
    {{ formattedDate }}
    <div class="colTime">
      {{ formattedTime }}
    </div>
  </div>
</template>

<script>
import { DATE_FORMAT, TIME_FORMAT } from "@/datetime";

export default {
  name: "DateTimeColumn",
  props: {
    dttm: {
      type: String,
      default: "",
    },
  },
  data() {
    return {
      date: new Date(this.dttm),
    };
  },
  computed: {
    formattedDate: function () {
      return DATE_FORMAT.format(this.date);
    },
    formattedTime: function () {
      return TIME_FORMAT.format(this.date);
    },
  },
  created() {},
};
</script>

<style scoped lang="scss">
.colTime {
  color: rgb(var(--v-theme-textDisabled)) !important;
}
</style>
