<template>
  <div v-if="displayValue" class="text">
    <div v-if="label" class="textLabel">
      {{ label }}
      <ExpandButton
        v-if="showExpandButton"
        class="expandButton"
        @click="expanded = true"
      />
    </div>
    <v-expand-transition>
      <div>
        <div :ref="textValueRefName" class="textValue" :style="textValueStyles">
          <span
            class="textContent"
            :class="classes"
            :title="title"
            @click="onClick"
          >
            {{ displayValue }}
          </span>
          <span v-if="baseName" class="textContent">{{ baseName }} </span>
        </div>
        <ExpandButton
          v-if="showExpandButton && !label"
          class="expandButton"
          @click="expanded = true"
        />
      </div>
    </v-expand-transition>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { formattedVolumeName } from "@/comic-name";
import ExpandButton from "@/components/metadata/expand-button.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "MetadataTextBox",
  components: {
    ExpandButton,
  },
  props: {
    group: {
      type: String,
      default: "",
    },
    highlight: {
      type: Boolean,
      default: false,
    },
    label: {
      // Body
      type: String,
      default: "",
    },
    maxHeight: {
      type: Number,
      default: 0,
    },
    value: {
      // Header -GroupObj, "text to Display",
      type: [Object, String, Number, Boolean],
      default: undefined,
    },
  },
  data() {
    return {
      mdiOpenInNew,
      expanded: false,
      mounted: false,
    };
  },
  computed: {
    ...mapState(useBrowserStore, ["groupNames"]),
    ...mapState(useBrowserStore, {
      browserShow: (state) => state.settings.show,
      browserTopGroup: (state) => state.settings.topGroup,
      folderViewEnabled: (state) => state.page.adminFlags.folderView,
    }),
    computedValue() {
      return this.value && this.value.name !== undefined
        ? this.value.name
        : this.value;
    },
    lastSlashIndex() {
      return this.computedValue.lastIndexOf("/") + 1;
    },
    displayValue() {
      let value;
      if (this.group === "f" && this.computedValue) {
        value = this.computedValue.slice(0, Math.max(0, this.lastSlashIndex));
      } else if (this.group === "v" && this.computedValue) {
        value = formattedVolumeName(this.computedValue, this.value.numberTo);
      } else {
        value = this.computedValue;
      }
      return value;
    },
    textValueStyles() {
      // makes expandable.
      const maxHeight =
        this.maxHeight > 0 && !this.expanded ? this.maxHeight : 0;
      if (maxHeight) {
        return "max-height: " + maxHeight + "px;";
      }
      return "";
    },
    textValueRefName() {
      const name = "mdTextValue" + this.label.replaceAll(" ", "");
      return name;
    },
    isOverflow() {
      if (!this.mounted) {
        return false;
      }
      const el = this.$refs[this.textValueRefName];
      if (!el) {
        return false;
      }
      return el.clientHeight < el.scrollHeight;
    },
    showExpandButton() {
      return !this.expanded && this.maxHeight > 0 && this.isOverflow;
    },
    linkPks() {
      const pks = this.value.ids || [this.value.pk];
      return pks.join(",");
    },
    clickable() {
      const params = this.$router.currentRoute.value.params;

      // Validate Group
      if (
        !this.group ||
        params.group === this.group ||
        (this.group === "f" && !this.folderViewEnabled) ||
        (!["a", "f"].includes(this.group) && !this.browserShow[this.group])
      ) {
        return false;
      }

      // Get & validate pks
      return Boolean(this.linkPks?.length);
    },
    classes() {
      return {
        clickable: this.clickable,
        highlight: this.highlight,
      };
    },
    toRoute() {
      // Using router-link gets hijacked and topGroup is not submitted.
      if (!this.clickable) {
        return "";
      }

      const group = this.group;
      const pks = this.linkPks;
      const params = { group, pks, page: 1 };
      return { name: "browser", params };
    },
    linkSettings() {
      const topGroup = this.getTopGroup(this.group);
      return { topGroup };
    },
    title() {
      let label;
      if (this.label) {
        label = this.label;
      } else if (this.group) {
        label = this.groupNames[this.group];
      } else {
        label = "";
      }
      return this.toRoute ? `Browse to ${label}` : label;
    },
    baseName() {
      return this.group === "f"
        ? this.computedValue.slice(Math.max(0, this.lastSlashIndex))
        : "";
    },
  },
  mounted() {
    this.mounted = true;
  },
  methods: {
    ...mapActions(useBrowserStore, ["routeWithSettings", "getTopGroup"]),
    onClick() {
      if (!this.clickable) {
        return;
      }
      this.routeWithSettings(this.linkSettings, this.toRoute);
    },
  },
};
</script>

<style scoped lang="scss">
@forward "../anchors";

.text {
  display: flex;
  flex-direction: column;
  padding: 10px;
  border-radius: 3px;
  max-width: 100%;
}

.textLabel {
  font-size: 12px;
  color: rgb(var(--v-theme-textSecondary));
}

.textContent {
  border: solid thin transparent;
}

.textValue {
  overflow-y: scroll;
}

.expandButton {
  float: right;
}

.clickable {
  cursor: pointer;
  color: rgb(var(--v-theme-primary));
}

.clickable:hover {
  color: white;
}

.highlight {
  padding: 0px 8px 0px 8px;
  border-radius: 12px;
  background-color: rgb(var(--v-theme-primary-darken-1));
}

.highlight {
  color: rgb(var(--v-theme-textPrimary)) !important;
  background-color: rgb(var(--v-theme-primary-darken-1));
}

.clickable.highlight:hover {
  border: solid thin rgb(var(--v-theme-textPrimary));
}
</style>
