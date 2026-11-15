import { dequal } from "dequal";
import { mapActions } from "pinia";

import { deepClone } from "@/api/v4/common";
import { useAdminStore } from "@/stores/admin";

/**
Mixin for create-update input components.

Required options for importing components:
  EMPTY_ROW  – with default field values
  UPDATE_KEYS – the keys sent on update

Provides:
  props.oldRow, emits["change"], data.row,
  watchers that sync row and oldRow and emit "change" (a refreshed oldRow
  keeps unsaved edits unless the server changed an UPDATE_KEYS field),
  and the nameSet action from the admin store.
*/
/*
 * ``deepClone`` (over ``structuredClone``) because ``oldRow`` rows
 * from the admin store carry reactive nested arrays (``groups``,
 * ``userSet``, ``librarySet``) that ``structuredClone`` can refuse
 * to clone.
 */
/** The fields a form edits, copied from a row. */
function editableValues(row, keys) {
  if (!row) return;
  const values = {};
  for (const key of keys) {
    Reflect.set(values, key, deepClone(Reflect.get(row, key)));
  }
  return values;
}

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
        ? { ...deepClone(emptyRow), ...deepClone(this.oldRow) }
        : deepClone(emptyRow),
      // The server's values for the edited fields when the form loaded.
      serverValues: editableValues(this.oldRow, this.$options.UPDATE_KEYS),
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
        if (!to) {
          this.row = deepClone(emptyRow);
          this.serverValues = undefined;
          return;
        }
        const keys = this.$options.UPDATE_KEYS;
        const row = { ...deepClone(emptyRow), ...deepClone(to) };
        const serverValues = editableValues(to, keys);
        /*
         * A table reload while the dialog is open (a WebSocket refresh,
         * or an action taken from inside the dialog) hands over a fresh
         * copy of the same row. Keep the admin's unsaved edits unless the
         * server changed a field this form edits.
         */
        if (dequal(serverValues, this.serverValues)) {
          for (const key of keys) {
            Reflect.set(row, key, Reflect.get(this.row, key));
          }
        }
        this.serverValues = serverValues;
        this.row = row;
      },
      deep: true,
    },
  },
  methods: {
    ...mapActions(useAdminStore, ["nameSet"]),
  },
};
