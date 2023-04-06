<template>
  <div class="pageError" :class="{ twoPages }">
    <div class="pageErrorContainer">
      <div class="pageErrorText">{{ text }}</div>
      <v-icon class="pageErrorIcon">{{ icon }}</v-icon>
    </div>
  </div>
</template>
<script>
import { mdiAlertCircleOutline, mdiLockOutline } from "@mdi/js";
const UNAUTHORIZED_TYPE = "unauthorized";

export default {
  name: "ErrorPage",
  props: {
    twoPages: { type: Boolean, required: true },
    type: { type: String, required: true },
  },
  computed: {
    text() {
      return this.type === UNAUTHORIZED_TYPE
        ? "Protected page"
        : "Failed to load page";
    },
    icon() {
      return this.type === UNAUTHORIZED_TYPE
        ? mdiLockOutline
        : mdiAlertCircleOutline;
    },
  },
};
</script>
<style scoped lang="scss">
.pageError {
  display: inline-block;
  height: 100vh;
}
.twoPages {
  max-width: 50vw;
}
.pageErrorContainer {
  display: grid;
  place-items: center;
  height: 100%;
}
.pageErrorText {
  position: relative;
  text-align: center;
  font-size: calc(100vw / 25);
  color: rgb(var(--v-theme-textDisabled));
  padding: 0.5em;
}
.pageErrorIcon {
  color: rgb(var(--v-theme-error));
  width: 75%;
  height: 75%;
  opacity: 0.33;
}
.pageErrorText,
.pageErrorIcon {
  grid-row: 1;
  grid-column: 1;
}
</style>
