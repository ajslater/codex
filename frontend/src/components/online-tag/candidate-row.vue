<!--
  One match candidate in the online-tagging review dialog.

  Two candidates routinely read identically — same series, issue and
  year — so the row has to carry enough to tell them apart: the cover,
  a link to the source's own page, and what the blended score is made
  of (#854).

  The thumbnail loads straight from the source CDN. An <img> is exempt
  from CORS, and codex's own img-src allows the two upload paths (see
  _ONLINE_TAG_COVER_SECURE_CSP), so there is nothing to proxy. A blocked
  or dead image falls back to the placeholder box, which keeps the rows
  aligned.
-->
<template>
  <div class="candidateRow">
    <img
      v-if="candidate.summary.coverUrl && !coverFailed"
      class="candidateCover"
      :src="candidate.summary.coverUrl"
      loading="lazy"
      referrerpolicy="no-referrer"
      alt=""
      @error="coverFailed = true"
    />
    <div v-else class="candidateCover candidateCoverPlaceholder" />
    <div class="candidateInfo">
      <strong>{{ candidate.summary.series }}</strong>
      <span v-if="candidate.summary.volume" class="candidateVolume">
        Vol. {{ candidate.summary.volume }}
      </span>
      <span v-if="candidate.summary.issue">
        #{{ candidate.summary.issue }}
      </span>
      <span v-if="candidate.summary.year" class="candidateYear">
        ({{ candidate.summary.year }})
      </span>
      <span v-if="candidate.summary.publisher" class="candidatePublisher">
        &mdash; {{ candidate.summary.publisher }}
      </span>
      <!-- eslint-disable-next-line sonarjs/no-vue-bypass-sanitization -->
      <a
        v-if="candidate.url"
        class="candidateSourceLink"
        :href="candidate.url"
        target="_blank"
        rel="noopener"
        >{{ sourceLabel(candidate.source) }}
        <v-icon size="x-small">{{ mdiOpenInNew }}</v-icon></a
      >
      <!-- Matching scores reprint series names too, so a comic filed
         under a localized title matches a series name that looks
         nothing like its filename. These are the reason. -->
      <div v-if="candidate.summary.altSeries?.length" class="candidateAka">
        a.k.a. {{ candidate.summary.altSeries.join(", ") }}
      </div>
      <div v-if="scoreDetail" class="candidateScoreDetail" :title="scoreTitle">
        {{ scoreDetail }}
      </div>
    </div>
    <v-chip size="x-small" class="ml-2">{{ scorePercent }}%</v-chip>
    <v-btn variant="tonal" size="small" color="primary" @click="$emit('pick')">
      Pick
    </v-btn>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";

import { sourceLabel } from "@/components/online-tag/source-labels";

const PERCENT = 100;

export default {
  name: "OnlineTagCandidateRow",
  props: {
    candidate: { type: Object, required: true },
  },
  emits: ["pick"],
  data() {
    return {
      mdiOpenInNew,
      coverFailed: false,
      blendedTitle: "Blended: 80% metadata and 20% cover comparison.",
      uncomparedTitle:
        "This candidate's cover wasn't compared, so its score is metadata only and isn't directly comparable to a blended one.",
    };
  },
  computed: {
    scorePercent() {
      return Math.round(this.candidate.score * PERCENT);
    },
    scoreDetail() {
      // Prompts cached before these fields existed carry neither, and
      // the headline percentage alone is still meaningful.
      const { metadataScore, coverScore } = this.candidate;
      if (metadataScore === undefined || metadataScore === null) {
        return "";
      }
      if (coverScore === undefined || coverScore === null) {
        // For an uncompared candidate the metadata score *is* the
        // headline number, so printing it again says nothing. The
        // caveat is the information.
        return "Cover not compared";
      }
      const md = Math.round(metadataScore * PERCENT);
      const cover = Math.round(coverScore * PERCENT);
      return `Match ${md}% · Cover ${cover}%`;
    },
    scoreTitle() {
      const { coverScore } = this.candidate;
      return coverScore === undefined || coverScore === null
        ? this.uncomparedTitle
        : this.blendedTitle;
    },
  },
  methods: {
    sourceLabel,
  },
};
</script>

<style scoped lang="scss">
.candidateRow {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.candidateCover {
  flex: 0 0 auto;
  width: 48px;
  height: 72px;
  object-fit: contain;
}

.candidateCoverPlaceholder {
  background-color: rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 2px;
}

.candidateInfo {
  flex: 1 1 auto;
  min-width: 0;
}

.candidateVolume,
.candidateYear,
.candidatePublisher,
.candidateAka,
.candidateScoreDetail {
  color: rgb(var(--v-theme-text-secondary));
}

.candidateAka,
.candidateScoreDetail {
  font-size: 0.8125rem;
}

.candidateSourceLink {
  margin-left: 8px;
  white-space: nowrap;
}
</style>
