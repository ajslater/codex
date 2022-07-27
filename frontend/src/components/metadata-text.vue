<template>
  <div v-if="computedValue" class="text" :class="{ highlight }">
    <div class="textLabel">{{ label }}</div>
    <a v-if="link" class="textLink" :href="computedValue" target="_blank">
      {{ computedValue }}
      <v-icon small color="rgba(204, 123, 25, 0.725)">
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
.text {
  display: flex;
  flex-direction: column;
  padding: 10px;
  background-color: #282828;
  border-radius: 3px;
  max-width: 100%;
}
.textLabel {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
}
.textContent {
  color: rgba(255, 255, 255, 0.8);
}

.textLink:link {
  color: rgba(204, 123, 25, 0.725);
  text-decoration: none;
}
.textLink:visited {
  color: rgba(204, 123, 25, 0.5);
}
.textLink:hover {
  color: rgba(204, 123, 25, 0.95);
}
.textLink:active {
  color: rgba(204, 123, 25, 1);
}
.highlight .textContent {
  background-color: rgba(204, 123, 25, 0.75);
  padding: 0px 8px 0px 8px;
  border-radius: 12px;
}
</style>
