<!--
  The file's own cover, in its prompt's expansion-panel title.

  Only the representative comic: the one the candidates were scored
  against. It shows at the candidates' 48x72 so the art compares at a
  glance. The thumbnail is Codex's own ACL-checked cover. The enlarge is
  page 0 from the reader, which is the same art, and it goes through the
  same CoverPopup as the candidates' covers, so it opens in the same capped
  box at the same size as theirs, never as a full-size page.

  The panel title is a <button> that toggles its panel, so a click on the
  cover stops at the cover: it opens the enlarge and leaves the panel
  alone. Vuetify's menu activator stops most of its clicks itself, but
  lets one through in the 50 ms after the enlarge closes, so the cover
  stops them all. The placeholder lets clicks through to the title.

  The backend reports whether the thumb exists yet. A missing one answers
  202 until the cover thread writes it, which an <img> cannot tell from a
  404, so a pending cover is probed with fetch first. That probe's GET is
  also what queues the generation. A placeholder says why in its tooltip.
-->
<template>
  <!-- Size goes in as props, not as a class: CoverPopup's popup branch
       is a VMenu fragment, and a scoped parent class cannot reach a
       multi-root child. -->
  <CoverPopup
    v-if="state === STATE.READY"
    :thumb-src="thumbSrc"
    :full-src="fullSrc"
    :thumb-width="COVER_WIDTH"
    :thumb-height="COVER_HEIGHT"
    :alt="alt"
    @click.stop
    @error="state = STATE.MISSING"
  />
  <div
    v-else
    class="fileCoverPlaceholder"
    role="img"
    :aria-label="note"
    :title="note"
  />
</template>

<script>
import { getCoverSrc } from "@/api/v4/browser";
import { COVER_PROBE, probeCover } from "@/api/v4/cover-probe";
import { getComicPageSource } from "@/api/v4/reader";
import CoverPopup from "@/components/cover-popup.vue";
import { COVER_HEIGHT, COVER_WIDTH } from "@/components/online-tag/cover-size";

// Mirrors _FileCoverStatus in codex/views/admin/onlinetag.py.
const FILE_COVER_STATUS = Object.freeze({
  READY: "ready",
  PENDING: "pending",
  FAILED: "failed",
});

const STATE = Object.freeze({
  READY: "ready",
  PROBING: "probing",
  PENDING: "pending",
  MISSING: "missing",
});

const STATE_BY_PROBE = Object.freeze({
  [COVER_PROBE.READY]: STATE.READY,
  [COVER_PROBE.PENDING]: STATE.PENDING,
  [COVER_PROBE.MISSING]: STATE.MISSING,
  [COVER_PROBE.ERROR]: STATE.MISSING,
});

export default {
  name: "OnlineTagFileCoverThumb",
  components: {
    CoverPopup,
  },
  props: {
    // {pk, mtime, status}, or null when the comic is no longer in the
    // library.
    fileCover: { type: Object, default: null },
  },
  data() {
    return {
      STATE,
      COVER_WIDTH,
      COVER_HEIGHT,
      state: STATE.MISSING,
      alt: "This file's cover",
      goneNote: "This file is no longer in the library",
      noCoverNote: "No cover available for this file",
      probingNote: "Loading cover…",
      pendingNote: "Cover is still being generated",
    };
  },
  computed: {
    thumbSrc() {
      if (!this.fileCover) return "";
      return getCoverSrc({ coverPk: this.fileCover.pk }, this.fileCover.mtime);
    },
    fullSrc() {
      if (!this.fileCover) return "";
      return getComicPageSource({
        pk: this.fileCover.pk,
        page: 0,
        mtime: this.fileCover.mtime,
        serve: "image",
      });
    },
    note() {
      switch (this.state) {
        case STATE.PROBING:
          return this.probingNote;
        case STATE.PENDING:
          return this.pendingNote;
        case STATE.MISSING:
          return this.fileCover ? this.noCoverNote : this.goneNote;
        default:
          return "";
      }
    },
    // A prompt reload hands over a new object each time; only a changed
    // value restarts, which is how a pending cover turns ready.
    coverKey() {
      const { pk, mtime, status } = this.fileCover || {};
      return `${pk}:${mtime}:${status}`;
    },
  },
  watch: {
    coverKey: {
      handler() {
        this.init();
      },
      immediate: true,
    },
  },
  beforeUnmount() {
    this.probeAbort?.abort();
  },
  methods: {
    init() {
      this.probeAbort?.abort();
      this.probeAbort = null;
      switch (this.fileCover?.status) {
        case FILE_COVER_STATUS.READY:
          this.state = STATE.READY;
          break;
        case FILE_COVER_STATUS.PENDING:
          this.state = STATE.PROBING;
          this.probe();
          break;
        default:
          // FAILED, or no comic at all.
          this.state = STATE.MISSING;
      }
    },
    async probe() {
      const controller = new AbortController();
      this.probeAbort = controller;
      const result = await probeCover(this.thumbSrc, {
        signal: controller.signal,
      });
      // Superseded by a newer init, or unmounted.
      if (controller.signal.aborted) return;
      this.state = STATE_BY_PROBE[result];
    },
  },
};
</script>

<style scoped lang="scss">
// Same box as candidate-row.vue's .candidateCoverPlaceholder, so a
// missing cover keeps the title's layout. Not getPlaceholderSrc: that
// needs CODEX.STATIC.
.fileCoverPlaceholder {
  flex: 0 0 auto;
  width: 48px;
  height: 72px;
  background-color: rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 2px;
}
</style>
