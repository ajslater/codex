<template>
  <div class="nameListEditor">
    <div v-if="items.length === 0" class="nameListEmpty">{{ emptyText }}</div>
    <v-list v-else class="nameList" density="compact">
      <template v-for="item of items" :key="item.pk">
        <div v-if="editingPk === item.pk" class="nameListEditRow">
          <v-text-field
            v-model="editName"
            autofocus
            class="nameListEditField"
            density="compact"
            :error-messages="editError"
            hide-details="auto"
            :label="renameTitle"
            :maxlength="maxLength"
            variant="outlined"
            @keydown.enter="onEnter"
            @keydown.esc.stop="cancelRename"
          />
          <v-btn
            class="nameListSaveBtn"
            density="compact"
            :disabled="!isEditValid"
            :icon="mdiCheck"
            size="small"
            title="Save"
            variant="text"
            @click="submitRename"
          />
          <v-btn
            class="nameListCancelBtn"
            density="compact"
            :icon="mdiClose"
            size="small"
            title="Cancel"
            variant="text"
            @click="cancelRename"
          />
        </div>
        <v-list-item
          v-else
          class="nameListRow"
          density="compact"
          :title="item.name"
          :subtitle="countLabel(item)"
        >
          <template #append>
            <slot name="actions" :item="item" />
            <v-btn
              class="nameListRenameBtn"
              density="compact"
              :icon="mdiPencil"
              size="small"
              :title="renameTitle"
              variant="text"
              @click="startRename(item)"
            />
            <v-btn
              class="nameListDeleteBtn"
              density="compact"
              :icon="mdiTrashCan"
              size="small"
              :title="deleteTitle"
              variant="text"
              @click="deleteTarget = item"
            />
          </template>
        </v-list-item>
      </template>
    </v-list>
    <ConfirmDialog
      :model-value="Boolean(deleteTarget)"
      confirm-text="Delete"
      :text="deleteText"
      :title-text="deleteTitle"
      @confirm="confirmDelete"
      @update:model-value="onDeleteDialog"
    />
  </div>
</template>

<script>
import { mdiCheck, mdiClose, mdiPencil, mdiTrashCan } from "@mdi/js";

import ConfirmDialog from "@/components/confirm-dialog.vue";
import { isImeEnter } from "@/util";

/*
 * A list of named things the user can rename and delete in place.
 * It owns no data: the parent passes ``items`` and acts on the
 * ``rename`` / ``delete`` events, so shelves and any later named list
 * (reading lists) share it. ``noun`` words the labels.
 */
export default {
  name: "NameListEditor",
  components: { ConfirmDialog },
  props: {
    // ``[{pk, name, count?}]`` in display order.
    items: {
      type: Array,
      required: true,
    },
    // What one item is called, lower case: "shelf".
    noun: {
      type: String,
      default: "item",
    },
    // What ``count`` counts, singular: "item" renders "3 items".
    countNoun: {
      type: String,
      default: "item",
    },
    emptyText: {
      type: String,
      default: "",
    },
    // Extra sentence for the delete confirmation.
    deleteHint: {
      type: String,
      default: "",
    },
    maxLength: {
      type: Number,
      default: 128,
    },
  },
  emits: ["delete", "rename"],
  data() {
    return {
      deleteTarget: null,
      editingPk: null,
      editName: "",
      mdiCheck,
      mdiClose,
      mdiPencil,
      mdiTrashCan,
    };
  },
  computed: {
    renameTitle() {
      return `Rename ${this.noun}`;
    },
    deleteTitle() {
      return `Delete ${this.noun}`;
    },
    deleteText() {
      const text = `Delete the ${this.noun} "${this.deleteTarget?.name ?? ""}"?`;
      return this.deleteHint ? `${text} ${this.deleteHint}` : text;
    },
    trimmedEditName() {
      return this.editName.trim();
    },
    isEditDuplicate() {
      return this.items.some(
        (item) =>
          item.pk !== this.editingPk && item.name === this.trimmedEditName,
      );
    },
    isEditValid() {
      return (
        this.trimmedEditName.length > 0 &&
        this.trimmedEditName.length <= this.maxLength &&
        !this.isEditDuplicate
      );
    },
    editError() {
      return this.isEditDuplicate
        ? `A ${this.noun} with this name already exists`
        : "";
    },
  },
  methods: {
    countLabel(item) {
      if (typeof item.count !== "number") return;
      const plural = item.count === 1 ? "" : "s";
      return `${item.count} ${this.countNoun}${plural}`;
    },
    startRename(item) {
      this.editingPk = item.pk;
      this.editName = item.name;
    },
    onEnter(event) {
      if (!isImeEnter(event)) this.submitRename();
    },
    cancelRename() {
      this.editingPk = null;
      this.editName = "";
    },
    submitRename() {
      if (!this.isEditValid) return;
      const item = this.items.find(({ pk }) => pk === this.editingPk);
      // An unchanged name is a cancel, not a request.
      if (item && item.name !== this.trimmedEditName) {
        this.$emit("rename", { pk: item.pk, name: this.trimmedEditName });
      }
      this.cancelRename();
    },
    onDeleteDialog(open) {
      if (!open) this.deleteTarget = null;
    },
    confirmDelete() {
      if (this.deleteTarget) {
        this.$emit("delete", this.deleteTarget.pk);
      }
      this.deleteTarget = null;
    },
  },
};
</script>

<style scoped lang="scss">
.nameList {
  padding-top: 0;
  padding-bottom: 0;
  background-color: transparent;
}

.nameListEmpty {
  padding: 5px 15px;
  color: rgb(var(--v-theme-text-disabled));
}

.nameListEditRow {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  padding: 5px 10px;
}

.nameListEditField {
  flex: 1;
}

.nameListSaveBtn,
.nameListCancelBtn {
  flex-shrink: 0;
  margin-top: 8px;
}
</style>
