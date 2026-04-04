import { mapActions } from "pinia";
import { toRaw } from "vue";

import { useAdminStore } from "@/stores/admin";

/**
 * Mixin for create-update input components.
 *
 * Required options for importing components:
 *   EMPTY_ROW  – with default field values
 *   UPDATE_KEYS – the keys sent on update
 *
 * Provides:
 *   props.oldRow, emits["change"], data.row,
 *   watchers that sync row and oldRow and emit "change",
 *   and the nameSet action from the admin store.
 */
export default {
  props: {
    oldRow: {
      type: [Object, Boolean],
      default: false,
    },
  },
  emits: ["change"],
  data() {
    const emptyRow = this.$options.EMPTY_ROW;
    return {
      row: this.oldRow
        ? {
            ...structuredClone(emptyRow),
            ...structuredClone(toRaw(this.oldRow)),
          }
        : structuredClone(emptyRow),
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
        const emptyRow = this.$options.EMPTY_ROW;
        this.row = to
          ? { ...structuredClone(emptyRow), ...structuredClone(toRaw(to)) }
          : structuredClone(emptyRow);
      },
      deep: true,
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["nameSet"]),
  },
};
