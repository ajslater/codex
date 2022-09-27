<template>
  <v-footer id="settingsFooter">
    <div id="opds" title="Copy OPDS URL to Clipboard" @click="copyToClipboard">
      <v-icon x-small>{{ mdiRss }}</v-icon
      >OPDS
      <v-icon id="clipBoardIcon" x-small color="gray">
        {{ clipBoardIcon }}
      </v-icon>
      <v-fade-transition>
        <span v-if="showTool" id="copied"> Copied </span>
      </v-fade-transition>
      <div id="opdsUrl">
        {{ opdsURL }}
      </div>
    </div>
    <a
      id="repo"
      href="https://github.com/ajslater/codex"
      title="Codex Source Repository"
    >
      repository<v-icon color="grey" x-small>{{ mdiOpenInNew }}</v-icon>
    </a>
  </v-footer>
</template>

<script>
import {
  mdiClipboardCheckOutline,
  mdiClipboardOutline,
  mdiOpenInNew,
  mdiRss,
} from "@mdi/js";

export default {
  name: "SettingsFooter",
  data() {
    return {
      mdiOpenInNew,
      mdiRss,
      opdsURL: window.origin + window.CODEX.OPDS_PATH,
      showTool: false,
    };
  },
  computed: {
    clipBoardIcon() {
      return this.showTool ? mdiClipboardCheckOutline : mdiClipboardOutline;
    },
  },
  methods: {
    copyToClipboard() {
      navigator.clipboard
        .writeText(this.opdsURL)
        .then(() => {
          this.showTool = true;
          setTimeout(() => {
            this.showTool = false;
          }, 5000);
          return true;
        })
        .catch((error) => {
          console.warn(error);
        });
    },
  },
};
</script>

<style scoped lang="scss">
#settingsFooter {
  width: 100%;
  display: block;
  padding-top: 5px;
  margin-top: auto;
  text-align: center;
  font-size: small;
  color: gray;
}
#settingsFooter * {
  width: 100%;
}
#opds {
  font-size: smaller;
  overflow-wrap: anywhere;
  color: grey;
  text-align: left;
  padding-bottom: 5px;
}
#opds * {
  padding: 0px;
  background-color: inherit;
  color: grey;
}
#copied {
  color: white;
  padding-left: 0.5em;
  display: inline;
}

/* eslint-disable-next-line vue-scoped-css/no-unused-selector */
#opds:hover #clipBoardIcon,
#opds:hover #opdsUrl {
  color: white;
}
#repo {
  color: gray;
}
#repo:hover {
  color: white;
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
#opds-header > .v-expansion-panel-header__icon {
  color: gray;
}
#opds-content > .v-expansion-panel-content__wrap {
  padding: 0px;
}
#repo:hover .v-icon {
  color: white !important;
}
</style>
