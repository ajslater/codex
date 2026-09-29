<!--
  The read state bar under a cover, shared by the browser card and the
  metadata dialog so the two never draw the same comic differently.
-->
<template>
  <div class="readState" :class="`is-${readState}`">
    <div class="readStateTrack">
      <div class="readStateFill" :style="fillStyle" />
    </div>
    <svg
      v-if="isFinished"
      class="readStateCap"
      viewBox="0 0 10 10"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="5" cy="5" r="5" />
      <polyline
        points="2.6,5.1 4.3,6.8 7.5,3.4"
        fill="none"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  </div>
</template>

<script>
import { getReadFillPercent, getReadState, READ_STATE } from "@/read-state";

export default {
  name: "ReadStateBar",
  props: {
    // A browser card or a metadata payload.
    item: {
      type: Object,
      required: true,
    },
  },
  computed: {
    readState() {
      return getReadState(this.item);
    },
    isFinished() {
      return this.readState === READ_STATE.FINISHED;
    },
    fillStyle() {
      return { width: `${getReadFillPercent(this.item)}%` };
    },
  },
};
</script>

<style scoped lang="scss">
/* Layered: these rules beat Vuetify's component CSS by position,
 * and lose to a `color`/utility prop, which is the intended order. */
@layer codex-components {
  /*
   * A fixed 10px slot with the 3px track centered in it. The slot is the
   * cap's height, so a finished card's footer sits level with its
   * neighbours' and no grid row gets a ragged baseline.
   */
  .readState {
    display: flex;
    align-items: center;
    width: 100%;
    height: 10px;
  }

  /*
   * Painted only where there is a fill to measure against. An always-on
   * track under every unread cover reads as a ruled grid, and unread is the
   * majority state in most libraries.
   */
  .readStateTrack {
    flex: 1 1 auto;
    height: 3px;
    border-radius: 2px;
    overflow: hidden;
    background-color: transparent;
  }

  .readStateFill {
    width: 0;
    height: 100%;
    border-radius: inherit;
    transition: width 0.15s;
  }

  .is-reading .readStateTrack,
  .is-finished .readStateTrack {
    background-color: rgba(var(--v-theme-text-disabled), 0.25);
  }

  /* Still reading: orange. Orange means one thing on this card. */
  .is-reading .readStateFill {
    background-color: rgb(var(--v-theme-primary));
  }

  /*
   * Finished: the cap carries the boolean, so the fill stays the real
   * bookmark position. A comic marked read but never opened is a bare track
   * and its cap. Neutral grey keeps a second hue out of the grid.
   */
  .is-finished .readStateFill {
    background-color: rgb(var(--v-theme-text-header));
  }

  /*
   * The track runs under the cap to its centre, so the two join with no
   * gap. The check is stroked in the page background rather than cut out,
   * because a cut-out would show the track through it.
   */
  .readStateCap {
    flex: none;
    width: 10px;
    height: 10px;
    margin-left: -5px;
  }

  .readStateCap circle {
    fill: rgb(var(--v-theme-text-header));
  }

  .readStateCap polyline {
    stroke: rgb(var(--v-theme-background));
  }

  @media (prefers-reduced-motion: reduce) {
    .readStateFill {
      transition: none;
    }
  }
}
</style>
