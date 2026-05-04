<template>
  <div class="bookCover">
    <v-img
      :src="imgSrc"
      :lazy-src="imgLazySrc"
      class="coverImg"
      :class="multiPkClasses"
      position="top"
    />
    <span v-if="group !== 'c'" class="childCount">
      {{ childCount }}
    </span>
  </div>
</template>

<script>
import { getCoverSrc, getPlaceholderSrc } from "@/api/v3/browser";

const MAX_RETRIES = 5;
const DEFAULT_RETRY_AFTER_SEC = 2;

export default {
  name: "BookCover",
  props: {
    group: {
      type: String,
      required: true,
    },
    pks: {
      type: Array,
      required: true,
    },
    coverPk: {
      type: Number,
      default: 0,
    },
    coverCustomPk: {
      type: Number,
      default: 0,
    },
    childCount: {
      type: Number,
      default: 1,
    },
    mtime: {
      type: Number,
      default: 0,
    },
  },
  data() {
    return {
      retry: 0,
      abort: null,
      missing: false,
    };
  },
  computed: {
    coverSrc() {
      const base = getCoverSrc(
        { coverPk: this.coverPk, coverCustomPk: this.coverCustomPk },
        this.mtime,
      );
      if (this.retry <= 0) {
        return base;
      }
      const sep = base.includes("?") ? "&" : "?";
      return `${base}${sep}r=${this.retry}`;
    },
    placeholderSrc() {
      return getPlaceholderSrc(this.group);
    },
    imgSrc() {
      /*
       * 404 → render the placeholder directly so it shows unblurred.
       * Otherwise use the cover URL; v-img shows the blurred lazy-src
       * until the real cover bytes arrive.
       */
      return this.missing ? this.placeholderSrc : this.coverSrc;
    },
    imgLazySrc() {
      /*
       * Skip lazy-src when missing so v-img doesn't apply its loading
       * blur to the static fallback.
       */
      return this.missing ? undefined : this.placeholderSrc;
    },
    multiPkClasses() {
      const len = this.pks.length;
      const classes = {};
      if (len >= 4) {
        classes["stack4"] = true;
      } else if (len > 1) {
        classes[`stack${len}`] = true;
      }
      return classes;
    },
  },
  mounted() {
    this.pollCover();
  },
  unmounted() {
    this.abort?.abort();
  },
  methods: {
    async pollCover() {
      /*
       * Probe the cover URL. The backend returns 202 Accepted with a
       * Cache-Control: no-store placeholder while the cover thread is still
       * generating the real thumb. Browsers don't honor Retry-After on <img>
       * elements, so we poll here and bump `retry` (a cache-busting query
       * param) to force v-img to re-fetch once the real cover is ready.
       */
      this.abort?.abort();
      this.abort = new AbortController();
      const signal = this.abort.signal;
      let sawPending = false;
      for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
        let resp;
        try {
          resp = await fetch(this.coverSrc, {
            credentials: "same-origin",
            signal,
          });
        } catch {
          return;
        }
        if (resp.status !== 202) {
          /*
           * 404 = no cover ever; switch to the unblurred placeholder.
           * Anything else (200, 5xx) leaves missing=false so v-img keeps
           * its lazy-blur loading state for src.
           */
          this.missing = resp.status === 404;
          if (sawPending && !this.missing) {
            this.retry = attempt + 1;
          }
          return;
        }
        sawPending = true;
        const retryAfterSec =
          Number.parseInt(resp.headers.get("Retry-After"), 10) ||
          DEFAULT_RETRY_AFTER_SEC;
        try {
          await new Promise((resolve, reject) => {
            const timer = setTimeout(resolve, retryAfterSec * 1000);
            signal.addEventListener("abort", () => {
              clearTimeout(timer);
              reject(new Error("aborted"));
            });
          });
        } catch {
          return;
        }
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";
@use "./book-cover" as bookcover;

.coverImg {
  height: bookcover.$cover-height;
  width: bookcover.$cover-width;
  border-radius: 5px;
}

/* Child Count - top right */
.childCount {
  position: absolute;
  top: 0px;
  right: 0px;
  min-width: 1.5rem;
  padding: 0rem 0.25rem 0rem 0.25rem;
  text-align: center;
  border-radius: 50%;
  background-color: rgb(var(--v-theme-background));
  color: rgb(var(--v-theme-textPrimary));
}

.stack2 {
  box-shadow: 3px 3px bookcover.$stack-shadow-1;
}

.stack3 {
  box-shadow:
    3px 3px bookcover.$stack-shadow-1,
    6px 6px bookcover.$stack-shadow-2;
}

.stack4 {
  box-shadow:
    3px 3px bookcover.$stack-shadow-1,
    6px 6px bookcover.$stack-shadow-2,
    9px 9px bookcover.$stack-shadow-3;
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  .coverImg {
    height: bookcover.$small-cover-height;
    width: bookcover.$small-cover-width;
  }
}
</style>
