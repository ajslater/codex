<!--
  One match candidate in the online-tagging review dialog.

  Two candidates routinely read identically — same series, issue and
  year — so the row has to carry enough to tell them apart: the cover,
  a link to the source's own page, and what the blended score is made
  of (#854).

  Covers are often near-identical too: a reprint volume, a foreign or a
  collected edition. So two subdued lines under the title carry what the
  source knows about the series (publisher, format, start year, issue
  count) and about the issue (its title and one-line deck). Comic Vine
  supplies most of it from rows comicbox already fetched. Metron always
  has the start year, but its format, publisher and issue count cost
  comicbox a request, so they arrive only when titles would otherwise
  collide. Any of it may be absent, and a prompt cached before comicbox
  carried it shows neither line.

  The thumbnail loads straight from the source CDN. An <img> is exempt
  from CORS, and codex's own img-src allows the two upload paths (see
  _ONLINE_TAG_COVER_SECURE_CSP), so there is nothing to proxy. A blocked
  or dead image falls back to the placeholder box, which keeps the rows
  aligned.

  Hovering enlarges the cover only when the source offers a larger tier.
  Comic Vine does; Metron sets coverUrlFull equal to coverUrl because its
  one image is already full size. The gate is "coverUrlFull is truthy",
  never "it differs from coverUrl" — comicbox owns that judgement. A
  prompt cached before the field existed simply has no affordance.
-->
<template>
  <div class="candidateRow">
    <!-- Size goes in as props, not as a class: CoverPopup's popup branch
         is a VMenu fragment, and a scoped parent class cannot reach a
         multi-root child. -->
    <CoverPopup
      v-if="candidate.summary.coverUrl && !coverFailed"
      :thumb-src="candidate.summary.coverUrl"
      :full-src="candidate.summary.coverUrlFull || ''"
      :thumb-width="COVER_WIDTH"
      :thumb-height="COVER_HEIGHT"
      alt=""
      @error="coverFailed = true"
    />
    <div v-else class="candidateCoverPlaceholder" />
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
      <div v-if="seriesDetail" class="candidateSeriesDetail">
        {{ seriesDetail }}
      </div>
      <!-- A deck can run long: clamped, the rest in the tooltip. -->
      <div v-if="issueDetail" class="candidateIssueDetail" :title="issueDetail">
        {{ issueDetail }}
      </div>
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
    <!-- Pinned, so long detail text wraps instead of squeezing them. -->
    <v-chip size="x-small" class="ml-2 flex-shrink-0">
      {{ scorePercent }}%
    </v-chip>
    <v-btn
      class="flex-shrink-0"
      variant="tonal"
      size="small"
      color="primary"
      @click="$emit('pick')"
    >
      Pick
    </v-btn>
  </div>
</template>

<script>
import { mdiOpenInNew } from "@mdi/js";

import CoverPopup from "@/components/cover-popup.vue";
import { COVER_HEIGHT, COVER_WIDTH } from "@/components/online-tag/cover-size";
import { sourceLabel } from "@/components/online-tag/source-labels";

const PERCENT = 100;

export default {
  name: "OnlineTagCandidateRow",
  components: {
    CoverPopup,
  },
  props: {
    candidate: { type: Object, required: true },
  },
  emits: ["pick"],
  data() {
    return {
      mdiOpenInNew,
      COVER_WIDTH,
      COVER_HEIGHT,
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
    seriesDetail() {
      const {
        seriesPublisher,
        publisher,
        seriesType,
        seriesStartYear,
        seriesIssueCount,
      } = this.candidate.summary;
      return [
        seriesPublisher || publisher,
        seriesType,
        seriesStartYear ? `Series began ${seriesStartYear}` : "",
        seriesIssueCount
          ? `${seriesIssueCount} ${seriesIssueCount === 1 ? "issue" : "issues"}`
          : "",
      ]
        .filter(Boolean)
        .join(" · ");
    },
    issueDetail() {
      const { issueTitle, issueSummary } = this.candidate.summary;
      return [issueTitle ? `“${issueTitle}”` : "", issueSummary]
        .filter(Boolean)
        .join(" — ");
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

// The placeholder only. The real thumbnail is CoverPopup's own <img>,
// sized by the props above.
.candidateCoverPlaceholder {
  flex: 0 0 auto;
  width: 48px;
  height: 72px;
  background-color: rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 2px;
}

.candidateInfo {
  flex: 1 1 auto;
  min-width: 0;
}

.candidateVolume,
.candidateYear,
.candidateSeriesDetail,
.candidateIssueDetail,
.candidateAka,
.candidateScoreDetail {
  color: rgb(var(--v-theme-text-secondary));
}

.candidateSeriesDetail,
.candidateIssueDetail,
.candidateAka,
.candidateScoreDetail {
  font-size: 0.8125rem;
}

// A deck can run long. Two lines, then an ellipsis: one line left a
// phone-width row about a dozen characters, and touch has no tooltip.
// Same multi-line clamp as browser-table-cell.vue.
.candidateIssueDetail {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: break-word;
}

.candidateSourceLink {
  margin-left: 8px;
  white-space: nowrap;
}
</style>
