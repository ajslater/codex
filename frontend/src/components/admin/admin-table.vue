<template>
  <v-table
    class="highlight-table admin-table"
    fixed-header
    :height="tableHeight"
  >
    <template #default>
      <thead>
        <slot name="thead" />
      </thead>
      <tbody :style="tbodyStyle">
        <slot name="tbody" />
      </tbody>
    </template>
  </v-table>
</template>

<script>
const FIXED_TOOLBARS = 96 + 16;
const ADD_HEADER = 36;
const TABLE_PADDING = 24;
const BUFFER_BASE = FIXED_TOOLBARS + ADD_HEADER + TABLE_PADDING;

const TABLE_ROW_HEIGHT = 48;
const MIN_TABLE_HEIGHT = TABLE_ROW_HEIGHT * 2;
const ROW_HEIGHT = 84;

export default {
  name: "AdminTable",
  props: {
    items: {
      type: Object,
      required: true,
    },
    extraHeight: {
      type: Number,
      default: 0,
    },
  },
  data() {
    return {
      innerHeight: window.innerHeight,
    };
  },
  computed: {
    numRows() {
      return this.items ? this.items.length : 0;
    },
    bufferHeight() {
      return BUFFER_BASE + this.extraHeight;
    },
    tableMaxHeight() {
      return this.numRows + 1 * TABLE_ROW_HEIGHT;
    },
    tableHeight() {
      const availableHeight = this.innerHeight - this.bufferHeight;
      return this.tableMaxHeight < availableHeight
        ? undefined
        : Math.max(availableHeight, MIN_TABLE_HEIGHT);
    },
    tbodyStyle() {
      return this.numRows ? { height: ROW_HEIGHT * this.numRows + "px" } : {};
    },
  },
  mounted() {
    window.addEventListener("resize", this.onResize);
  },
  methods: {
    onResize() {
      this.innerHeight = window.innerHeight;
    },
  },
};
</script>
<style scoped lange="scss">
.admin-table {
  max-width: 100vw !important;
  margin-bottom: 24px;
}
:deep(.tableCheckbox) {
  height: 40px;
}
</style>
