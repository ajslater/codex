<template>
  <a
    id="repo"
    href="https://github.com/ajslater/codex"
    title="Codex Source Repository"
    target="_blank"
  >
    <v-icon id="repoIcon" size="x-small">{{ mdiSourceRepository }}</v-icon>
    repository<v-icon
      :color="$vuetify.theme.current.colors.iconsInactive"
      size="x-small"
      >{{ mdiOpenInNew }}</v-icon
    >
  </a>
</template>

<script>
import { mdiOpenInNew, mdiSourceRepository } from "@mdi/js";

export default {
  name: "RepoFooter",
  data() {
    return {
      mdiOpenInNew,
      mdiSourceRepository,
    };
  },
};
</script>

<style scoped lang="scss">
#repo {
  display: block;
  width: 100%;
  color: rgb(var(--v-theme-textDisabled));
}
#repo:hover {
  color: rgb(var(--v-theme-textPrimary));
}
#repoIcon {
  margin-right: 0px;
}
#repo:hover > #repoIcon {
  color: rgb(var(--v-theme-textPrimary)) !important;
}
</style>
