<template>
  <v-toolbar id="browserToolbarTitle" :height="24" :extension-height="24">
    <v-toolbar-title id="browserTitle" class="browserTitle">
      {{ title }}
    </v-toolbar-title>
    <template v-if="subtitle" #extension>
      <v-toolbar-title id="browserSubtitle" class="browserTitle">
        {{ subtitle }}
      </v-toolbar-title>
    </template>
  </v-toolbar>
</template>

<script>
import { mdiReload } from "@mdi/js";
import { mapState } from "pinia";

import { formattedVolumeName } from "@/comic-name";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserHeader",
  data() {
    return {
      mdiReload,
    };
  },
  head() {
    const titleSuffix = this.subtitle ? this.subtitle : this.title;
    const title = "Browse / " + titleSuffix;
    const names = ["browse comics", this.title, this.subtitle];
    const content = names.filter(Boolean).join(" ");
    return {
      title,
      meta: [{ hid: "description", name: "description", content }],
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      browserTitle: (state) => state.page?.title,
      groupNames: (state) => state.choices.static.groupNames,
      modelGroup: (state) => state.page.modelGroup,
    }),
    ...mapState(useAuthStore, ["isUserAdmin"]),
    title() {
      let title;
      if (Number(this.$route.params.pks) === 0) {
        title = "All";
      } else if (this.browserTitle) {
        let names = [];
        const { groupName, groupNumberTo, groupCount } = this.browserTitle;
        const group = this.$route.params.group;
        const formattedGroupName =
          group === "v"
            ? formattedVolumeName(groupName, groupNumberTo)
            : groupName;
        if (formattedGroupName) {
          names.push(formattedGroupName);
        }
        if (groupCount) {
          const formattedGroupCount = `of ${groupCount}`;
          names.push(formattedGroupCount);
        }
        title = names.join(" ");
      } else {
        title = "(Empty)";
      }
      return title;
    },
    subtitle() {
      return this.$route.params.group === "f"
        ? ""
        : this.groupNames[this.modelGroup];
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;

#browserToolbarTitle {
  padding-bottom: 6px;
}

.browserTitle {
  margin: 0px;
  text-align: center;
  white-space: nowrap;
  overflow-y: scroll;
}

#browserTitle {
  font-size: clamp(12px, 2vw, 20px);
}

#browserSubtitle {
  padding-top: 2px;
  font-size: 15px;
  color: rgb(var(--v-theme-textDisabled));
}
</style>
