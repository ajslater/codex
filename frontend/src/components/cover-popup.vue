<!--
  A cover thumbnail that opens its full-size image on hover, click or the
  keyboard.

  The affordance exists only when `fullSrc` is truthy. That is the whole
  gate: a source that offers no larger tier gets a plain <img> with no
  cursor change, no role and no menu, so nothing promises an enlargement
  that does not exist. Never fall back to `thumbSrc` — the caller's
  source decides whether a bigger image exists, and Metron deliberately
  sets the two equal because its one image is already full size.

  Vuetify mounts overlay content on first activation and tears it down
  after close, so a re-hover re-requests the image from the browser or
  CDN cache. Match candidates load straight from the source's CDN, which
  is why neither image carries `crossorigin` (an <img> is CORS-exempt)
  and both send no referrer. Codex's own covers and pages come through
  here too, and both attributes are harmless on a same-origin image.

  Every enlarge renders in the same capped box (.coverPopupBody img), so
  a full comic page opens at the same size as a CDN's large tier. One
  that fails to load says so rather than leaving an empty shadowed box.
-->
<template>
  <v-menu
    v-if="fullSrc"
    v-model="open"
    open-on-hover
    open-on-click
    :close-on-content-click="false"
    location="end center"
    offset="8"
    transition="scale-transition"
    origin="overlap"
  >
    <template #activator="{ props: menuProps }">
      <slot name="thumb" :props="activatorBindings(menuProps)">
        <img
          v-bind="activatorBindings(menuProps)"
          :src="thumbSrc"
          :alt="alt"
          :title="title"
          :style="thumbStyle"
          class="coverPopupThumb coverPopupZoomable"
          :loading="loading"
          referrerpolicy="no-referrer"
          @error="$emit('error', $event)"
        />
      </slot>
    </template>
    <div class="coverPopupBody">
      <img
        v-if="!fullFailed"
        :src="fullSrc"
        :alt="alt"
        loading="lazy"
        referrerpolicy="no-referrer"
        @error="fullFailed = true"
      />
      <div v-else class="coverPopupError">{{ fullErrorText }}</div>
    </div>
  </v-menu>
  <slot v-else name="thumb" :props="plainBindings">
    <img
      v-bind="plainBindings"
      :src="thumbSrc"
      :alt="alt"
      :title="title"
      :style="thumbStyle"
      class="coverPopupThumb"
      :loading="loading"
      referrerpolicy="no-referrer"
      @error="$emit('error', $event)"
    />
  </slot>
</template>

<script>
import { mergeProps } from "vue";

export default {
  name: "CoverPopup",
  // $attrs go onto the <img>, not onto VMenu's fragment root.
  inheritAttrs: false,
  props: {
    thumbSrc: { type: String, required: true },
    fullSrc: { type: String, default: "" },
    alt: { type: String, default: "cover" },
    title: { type: String, default: "" },
    // Inline, not a class: a parent's scoped style cannot reach a
    // multi-root child, and VMenu renders a Fragment.
    thumbWidth: { type: String, default: "" },
    thumbHeight: { type: String, default: "" },
    /*
     * Lazy suits a long list of remote images. It does NOT suit a
     * thumbnail sized `width: auto`: before the image loads such an
     * element has zero width, a zero-area element never satisfies the
     * browser's in-viewport check, and the load never starts — the
     * image stays 0×h forever. Pass "eager" there.
     */
    loading: { type: String, default: "lazy" },
    activatorProps: { type: Object, default: () => ({}) },
  },
  emits: ["error"],
  data() {
    return {
      open: false,
      fullFailed: false,
      fullErrorText: "Full-size image unavailable",
    };
  },
  computed: {
    thumbStyle() {
      const style = {};
      if (this.thumbWidth) style.width = this.thumbWidth;
      if (this.thumbHeight) style.height = this.thumbHeight;
      return style;
    },
    plainBindings() {
      return mergeProps(this.$attrs, this.activatorProps);
    },
  },
  watch: {
    open(isOpen) {
      // Each opening retries, as the re-mounted overlay would anyway.
      if (isOpen) this.fullFailed = false;
    },
  },
  methods: {
    activatorBindings(menuProps) {
      // mergeProps chains handlers rather than replacing them, so
      // VMenu's own onKeydown survives alongside this one.
      return mergeProps(menuProps, this.$attrs, this.activatorProps, {
        role: "button",
        tabindex: 0,
        "aria-label": "Show full-size cover",
        onKeydown: this.onKeydown,
      });
    },
    onKeydown(event) {
      if (event.key !== "Enter" && event.key !== " ") return;
      // Space would scroll the dialog out from under the popup.
      event.preventDefault();
      this.open = !this.open;
    },
  },
};
</script>

<style scoped lang="scss">
.coverPopupThumb {
  display: block;
  flex: 0 0 auto;
  object-fit: contain;
}

.coverPopupZoomable {
  cursor: zoom-in;
}

.coverPopupBody {
  display: block;
  cursor: zoom-out;
}

.coverPopupBody img {
  display: block;
  max-height: 70vh;
  max-width: 60vw;
  border-radius: 4px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.55);
}

.coverPopupError {
  padding: 8px 12px;
  border-radius: 4px;
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-text-secondary));
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.55);
}
</style>
