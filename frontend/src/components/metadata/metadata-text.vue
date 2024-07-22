<template>
  <div v-if="computedValue" class="text" :class="{ highlight }">
    <div class="textLabel">
      {{ label }}
    </div>
    <div class="textValue" :class="{ empty }">
      <router-link
        v-if="groupTo && group === 'f'"
        id="folderPath"
        :to="groupTo"
        title="Browse Folder"
      >
        {{ folderPath }}/
      </router-link>
      <router-link
        v-else-if="groupTo"
        class="textContent"
        :to="groupTo"
        :title="`Browse ${label}`"
      >
        {{ computedValue }}
      </router-link>
      <a v-else-if="link" :href="linkValue" target="_blank">
        {{ computedValue }}
        <v-icon size="small">
          {{ mdiOpenInNew }}
        </v-icon>
      </a>
      <div v-else class="textContent">
        {{ computedValue }}
      </div>
      <span v-if="groupTo && group === 'f'" id="basePath">{{ basePath }} </span>
    </div>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapState } from "pinia";

import { GROUPS_REVERSED, useBrowserStore } from "@/stores/browser";

const EMPTY_VALUE = "(Empty)";

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
      type: [Boolean, String],
      default: false,
    },
    group: {
      type: String,
      default: "",
    },
    obj: {
      type: Object,
      default: undefined,
    },
  },
  data() {
    return {
      mdiOpenInNew,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      browserShow: (state) => state.settings.show,
      browserTopGroup: (state) => state.settings.topGroup,
      folderViewEnabled: (state) => state.page.adminFlags.folderView,
    }),
    computedValue() {
      let value =
        this.value && this.value.name !== undefined
          ? this.value.name
          : this.value;
      if (this.group && value === "") {
        value = EMPTY_VALUE;
      }
      return value;
    },
    empty() {
      return this.computedValue === EMPTY_VALUE;
    },
    linkValue() {
      if (this.link === true) {
        return this.computedValue;
      } else if (this.link) {
        return this.link;
      }
      return false;
    },
    highlight() {
      return this.obj?.group === this.group;
    },
    pathArray() {
      if (!this.computedValue) {
        return;
      }
      return this.computedValue.split("/");
    },
    folderPath() {
      if (!this.pathArray) {
        return;
      }
      return this.pathArray.slice(0, -1).join("/");
    },
    basePath() {
      if (!this.pathArray) {
        return;
      }
      return this.pathArray.at(-1);
    },
    groupTo() {
      const group = this.group;
      const params = this.$router.currentRoute.value.params;
      if (
        !group ||
        params.group === group ||
        (group === "f" && !this.folderViewEnabled) ||
        (!["a", "f"].includes(group) && !this.browserShow[group])
      ) {
        return;
      }
      const pksList = this.value.ids ? this.value.ids : [this.value.pk];
      const pks = pksList.join(",");

      if (!pks || params.pks === pks) {
        return;
      }
      const topGroup = this.getTopGroup(group);
      return { name: "browser", params: { group, pks }, query: { topGroup } };
    },
  },
  methods: {
    getTopGroup(group) {
      // Very similar to browser store logic, could possibly combine.
      let topGroup;
      if (this.browserTopGroup === group || ["a", "f"].includes(group)) {
        topGroup = group;
      } else {
        const groupIndex = GROUPS_REVERSED.indexOf(group);
        // Determine browse top group
        for (const testGroup of GROUPS_REVERSED.slice(groupIndex)) {
          if (testGroup === "r" || this.browserShow[testGroup]) {
            topGroup = testGroup;
          }
        }
      }
      return topGroup;
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

.textContent {
  border: solid thin transparent;
}

.highlight .textContent {
  background-color: rgb(var(--v-theme-primary-darken-1));
  padding: 0px 8px 0px 8px;
  border-radius: 12px;
}

// eslint-disable-next-line vue-scoped-css/no-unused-selector
.highlight a.textContent {
  color: rgb(var(--v-theme-textPrimary)) !important;
  background-color: rgb(var(--v-theme-primary-darken-1));
}

// eslint-disable-next-line vue-scoped-css/no-unused-selector
.highlight a.textContent:hover {
  border: solid thin rgb(var(--v-theme-textPrimary));
}

.empty {
  opacity: 0.5;
}
</style>
