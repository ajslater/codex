/**
 * Reactive "now" timestamp that ticks every second.
 *
 * Used by: job-tab.vue, status-list.vue
 */
import { ref, onMounted, onUnmounted } from "vue";

const TICK_INTERVAL_MS = 1000;

/**
 * Returns a reactive `now` ref (Date.now()) that auto-updates every second
 * while the component is mounted. Cleans up on unmount.
 */
export function useNowTimer() {
  const now = ref(Date.now());
  let timer = 0;

  const start = () => {
    stop();
    timer = globalThis.setInterval(() => {
      now.value = Date.now();
    }, TICK_INTERVAL_MS);
  };

  const stop = () => {
    if (timer) {
      globalThis.clearInterval(timer);
      timer = 0;
    }
  };

  onMounted(start);
  onUnmounted(stop);

  return { now };
}
