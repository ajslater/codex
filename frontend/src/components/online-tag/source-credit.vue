<!--
  The credit a source's terms require wherever its data is shown, linked to
  the source. comicbox supplies the words and the link (tagging-attribution
  .json); a source that asks for no credit renders nothing.
-->
<template>
  <div v-if="credit" class="sourceCredit">
    <a :href="credit.url" target="_blank" rel="noopener noreferrer"
      >{{ credit.text
      }}<v-icon size="x-small" class="sourceCreditIcon">{{
        mdiOpenInNew
      }}</v-icon></a
    >
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";

import { sourceAttribution } from "@/components/online-tag/source-labels";

export default {
  name: "SourceCredit",
  props: {
    source: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      mdiOpenInNew,
    };
  },
  computed: {
    credit() {
      return sourceAttribution(this.source);
    },
  },
};
</script>

<style scoped lang="scss">
.sourceCredit {
  font-size: 0.8em;
  color: rgb(var(--v-theme-text-secondary));
}

.sourceCreditIcon {
  margin-left: 2px;
}
</style>
