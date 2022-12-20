<template>
  <div v-if="computedValue" class="text" :class="{ highlight }">
    <div class="textLabel">
      {{ label }}
    </div>
    <a v-if="link" :href="computedValue" target="_blank">
      {{ computedValue }}
      <v-icon size="small">
        {{ mdiOpenInNew }}
      </v-icon>
    </a>
    <div v-else class="textContent">
      {{ computedValue }}
    </div>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";

export default {
  name: "MetadataTextBox",
  props: {
    label: {
      type: String,
      required: true,
    },
    value: {
      type: [Object, String, Number, Boolean],
      default: undefined,
    },
    link: {
      type: Boolean,
      default: false,
    },
    highlight: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      mdiOpenInNew,
    };
  },
  computed: {
    computedValue: function () {
      return this.value != undefined && this.value instanceof Object
        ? this.value.name
        : this.value;
    },
  },
};
</script>

<style scoped lang="scss">
@import "../anchors.scss";
.text {
  display: flex;
  flex-direction: column;
  padding: 10px;
  border-radius: 3px;
  max-width: 100%;
  background-color: rgb(var(--v-theme-surface));
}
.textLabel {
  font-size: 12px;
  color: rgb(var(--v-theme-textSecondary));
}
.highlight .textContent {
  background-color: rgb(var(--v-theme-primary-darken-1));
  padding: 0px 8px 0px 8px;
  border-radius: 12px;
}
</style>
