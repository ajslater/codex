<template>
  <!-- Collapsed: most people never set up KOReader. -->
  <v-expansion-panels class="koreaderHelp">
    <v-expansion-panel>
      <v-expansion-panel-title>KOReader setup</v-expansion-panel-title>
      <v-expansion-panel-text class="koreaderHelpText">
        <p>
          In KOReader open a book, then <b>Progress sync</b>: set
          <b>Custom sync server</b> to the URL above, then use
          <b>Register / Login</b> to log in with your Codex username<template
            v-if="username"
          >
            (<b>{{ username }}</b
            >)</template
          >
          and a Device Key as the password.
        </p>
        <p>
          <b>Document matching method</b> (a KOReader setting): leave it on
          <b>Binary</b>, which recognizes a comic by its file contents. Switch
          to <b>Filename</b> if you edit tags in Codex: saving tags rewrites the
          file, so a copy already on your device stops matching by contents.
        </p>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script>
export default {
  name: "KOReaderHelp",
  props: {
    username: { type: String, default: "" },
  },
};
</script>

<style scoped lang="scss">
.koreaderHelpText {
  font-size: small;
  color: rgb(var(--v-theme-text-secondary));
}

.koreaderHelpText p + p {
  margin-top: 0.5em;
}
</style>
