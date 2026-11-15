<template>
  <v-dialog
    v-model="showDialog"
    origin="center-top"
    transition="slide-y-transition"
    max-width="512"
  >
    <template #activator="{ props }">
      <v-btn
        :prepend-icon="mdiCellphoneKey"
        v-bind="props"
        text="Device Keys"
      />
    </template>
    <div id="deviceKeysDialog">
      <h2>Device Keys</h2>
      <p class="deviceKeysHelp">
        Give each reader app or device its own key. A key logs in to OPDS and
        KOReader sync only, and can be revoked on its own.
      </p>
      <table v-if="deviceKeys.length" class="deviceKeysTable">
        <thead>
          <tr>
            <th>Name</th>
            <th>Key</th>
            <th>Last used</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in deviceKeys" :key="row.pk">
            <td>{{ row.name }}</td>
            <td class="keyPrefix">{{ row.prefix }}…</td>
            <td>{{ lastUsed(row) }}</td>
            <td>
              <v-btn
                size="small"
                variant="text"
                :color="confirmPk === row.pk ? 'error' : undefined"
                :prepend-icon="mdiKeyRemove"
                :text="confirmPk === row.pk ? 'Confirm' : 'Revoke'"
                :title="`Revoke ${row.name}`"
                @click.stop="revoke(row.pk)"
              />
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="deviceKeysHelp">No device keys yet.</p>

      <div v-if="newKey" class="newKey">
        <ClipBoard
          :tooltip="TOOLTIP"
          :title="`Key for ${newKeyName}`"
          subtitle="Copy it now: it is shown only this once."
          :text="newKey"
        />
        <table class="usageTable">
          <tbody>
            <tr>
              <td>OPDS</td>
              <td class="helpValue">
                Username <b>{{ username }}</b> with this key as the password, or
                the header <code>Authorization: Bearer {{ newKey }}</code>
              </td>
            </tr>
            <tr>
              <td>KOReader</td>
              <td class="helpValue">
                Username <b>{{ username }}</b> with this key as the password
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <v-form class="createForm" @submit.prevent="create">
        <v-text-field
          v-model="name"
          label="New key name"
          placeholder="Kobo Libra"
          :maxlength="NAME_MAX_LENGTH"
          :error-messages="formErrors"
          density="compact"
          clearable
        />
        <v-btn
          type="submit"
          :prepend-icon="mdiKeyPlus"
          :disabled="!canCreate"
          text="Create"
        />
      </v-form>
    </div>
  </v-dialog>
</template>

<script>
import { mdiCellphoneKey, mdiKeyPlus, mdiKeyRemove } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ClipBoard from "@/components/clipboard.vue";
import { getDateTime } from "@/datetime";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const TOOLTIP = "Copy device key to clipboard";
// UserApiKey.name's max_length.
const NAME_MAX_LENGTH = 64;

export default {
  name: "DeviceKeysDialog",
  components: {
    ClipBoard,
  },
  data() {
    return {
      mdiCellphoneKey,
      mdiKeyPlus,
      mdiKeyRemove,
      NAME_MAX_LENGTH,
      TOOLTIP,
      showDialog: false,
      name: "",
      newKey: "",
      newKeyName: "",
      confirmPk: undefined,
    };
  },
  computed: {
    ...mapState(useAuthStore, ["deviceKeys", "user"]),
    ...mapState(useCommonStore, {
      formErrors: (state) => state.form.errors,
    }),
    username() {
      return this.user?.username || "";
    },
    canCreate() {
      return Boolean(this.name?.trim());
    },
  },
  watch: {
    showDialog(open) {
      // The key is never shown again once the dialog closes.
      this.newKey = "";
      this.newKeyName = "";
      this.confirmPk = undefined;
      this.clearErrors();
      if (open) {
        this.loadDeviceKeys();
      }
    },
  },
  methods: {
    ...mapActions(useAuthStore, [
      "loadDeviceKeys",
      "createDeviceKey",
      "deleteDeviceKey",
    ]),
    ...mapActions(useCommonStore, ["clearErrors"]),
    lastUsed(row) {
      return row.lastUsedAt ? getDateTime(row.lastUsedAt) : "Never";
    },
    async create() {
      if (!this.canCreate) {
        return;
      }
      const name = this.name.trim();
      const key = await this.createDeviceKey(name);
      if (key) {
        this.newKey = key;
        this.newKeyName = name;
        this.name = "";
      }
    },
    async revoke(pk) {
      if (this.confirmPk !== pk) {
        this.confirmPk = pk;
        return;
      }
      this.confirmPk = undefined;
      await this.deleteDeviceKey(pk);
    },
  },
};
</script>

<style scoped lang="scss">
#deviceKeysDialog {
  padding: 20px;
}

.deviceKeysHelp {
  color: rgb(var(--v-theme-text-disabled));
  padding-bottom: 1em;
}

.deviceKeysTable,
.usageTable {
  width: 100%;
  padding-bottom: 1em;
}

.deviceKeysTable th {
  text-align: left;
  color: rgb(var(--v-theme-text-disabled));
}

.deviceKeysTable td,
.usageTable td {
  padding: 4px;
}

.keyPrefix {
  font-family: monospace;
}

.newKey {
  padding-bottom: 1em;
}

.helpValue {
  border-radius: 5px;
  background-color: rgb(var(--v-theme-surface));
  overflow-wrap: anywhere;
}

.createForm {
  display: flex;
  gap: 0.5em;
  align-items: baseline;
}
</style>
