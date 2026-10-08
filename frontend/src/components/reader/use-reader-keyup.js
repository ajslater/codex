/**
Document keyup listener for the reader's keyboard shortcuts that ignores keys
meant for a dialog or menu open over the reader.

Used by: reader-toolbar-top.vue, reader-toolbar-nav.vue,
reader-settings-scope.vue
*/
import { useEventListener } from "@vueuse/core";

const OVERLAY_SELECTOR = ".v-overlay";

export function isInOverlay(target) {
  return Boolean(target?.closest?.(OVERLAY_SELECTOR));
}

/**
Calls `listener` on document keyup unless the key went to a Vuetify overlay.

Vuetify closes an overlay on Escape keydown and focuses its activator, so by
keyup neither the target nor the overlay's state shows the key was the
overlay's. Decide on keydown instead; the capture phase still sees keydowns
the overlay stops.
*/
export function useReaderKeyUp(listener) {
  const overlayKeys = new Set();
  useEventListener(
    document,
    "keydown",
    (event) => {
      // Holding a key repeats keydown wherever the first one moved focus.
      if (event.repeat) {
        return;
      }
      if (isInOverlay(event.target)) {
        overlayKeys.add(event.code);
      } else {
        overlayKeys.delete(event.code);
      }
    },
    { capture: true },
  );
  useEventListener(document, "keyup", (event) => {
    const pressedInOverlay = overlayKeys.delete(event.code);
    if (pressedInOverlay || isInOverlay(event.target)) {
      return;
    }
    listener(event);
  });
}
