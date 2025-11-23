<template>
  <a
    id="repo"
    href="https://codex-comic-reader.readthedocs.io/"
    title="Codex Documentation"
    target="_blank"
  >
    <v-icon id="repoIcon" size="x-small">{{
      mdiBookOpenVariantOutline
    }}</v-icon>
    documentation<v-icon size="x-small">{{ mdiOpenInNew }}</v-icon>
  </a>
</template>

<script>
import { mdiBookOpenVariantOutline, mdiOpenInNew } from "@mdi/js";

export default {
  name: "DocsFooter",
  data() {
    return {
      mdiBookOpenVariantOutline,
      mdiOpenInNew,
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
</style>
