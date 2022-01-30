<template>
  <div v-if="computedValue" class="text">
    <div class="textLabel">{{ label }}</div>
    <a v-if="link" class="textLink" href="computedValue">
      {{ computedValue }}
    </a>
    <div v-else class="textContent">
      {{ computedValue }}
    </div>
  </div>
</template>

<script>
export default {
  name: "MetadataTextBox",
  props: {
    label: {
      type: String,
      required: true,
    },
    value: {
      type: [Object, String, Number],
      default: undefined,
    },
    link: {
      type: Boolean,
      default: false,
    },
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
  padding-left: 10px;
  padding-right: 10px;
  padding-top: 10px;
  background-color: #282828;
  border-bottom: solid thin;
  border-color: rgba(255, 255, 255, 0.7);
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
</style>
