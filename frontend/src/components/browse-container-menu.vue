<template>
  <v-menu offset-y top>
    <template #activator="{ on }">
      <v-icon class="actionMenu" v-on="on">{{ mdiDotsVertical }}</v-icon>
    </template>
    <v-list>
      <v-list-item>
        <v-checkbox
          label="read"
          :input-value="finished"
          :indeterminate="finished === null"
          class="readCheckbox"
          dense
          hide-details
          @change="markRead(group, pk, $event === true)"
        />
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script>
import { mdiDotsVertical } from "@mdi/js";
import { mapState } from "vuex";

export default {
  name: "BrowseContainerMenu",
  props: {
    group: {
      type: String,
      required: true,
    },
    pk: {
      type: Number,
      required: true,
    },
    finished: {
      type: Boolean,
    },
  },
  data() {
    return {
      mdiDotsVertical,
    };
  },
  computed: {
    ...mapState("reader", {}),
  },
  methods: {
    markRead: function (group, pk, finished) {
      this.$store.dispatch("browser/markRead", { group, pk, finished });
    },
  },
};
</script>

<style scoped lang="scss">
.actionMenu {
  position: absolute;
  bottom: 3px;
  right: 3px;
}
.readCheckbox {
  padding: 0px;
  margin: 0px;
}
</style>
