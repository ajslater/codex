// v-drag-scroll directive
const DRAG_THRESHOLD = 4; // pixels before we commit to a drag

const dragScrollDirective = {
  mounted(el, binding) {
    const onlyX = binding.modifiers.onlyX;
    const onlyY = binding.modifiers.onlyY;
    let startX = 0;
    let startY = 0;
    let scrollLeft = 0;
    let scrollTop = 0;
    let pointerId = null;
    let dragging = false;

    const onPointerDown = (e) => {
      // Don't intercept clicks on interactive children
      if (e.target.closest("button, a, input, [role=button]")) return;
      startX = e.clientX;
      startY = e.clientY;
      scrollLeft = el.scrollLeft;
      scrollTop = el.scrollTop;
      pointerId = e.pointerId;
      dragging = false; // not committed yet
    };

    const onPointerMove = (e) => {
      if (pointerId === null) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (!dragging) {
        // Only commit to drag once threshold is exceeded
        if (Math.abs(dx) < DRAG_THRESHOLD && Math.abs(dy) < DRAG_THRESHOLD)
          return;
        dragging = true;
        el.setPointerCapture(pointerId);
        el.style.cursor = "grabbing";
      }
      if (!onlyY) el.scrollLeft = scrollLeft - dx;
      if (!onlyX) el.scrollTop = scrollTop - dy;
    };

    const onPointerUp = () => {
      if (dragging && pointerId !== null) {
        el.releasePointerCapture(pointerId);
        el.style.cursor = "";
      }
      pointerId = null;
      dragging = false;
    };

    el._dragScroll = { onPointerDown, onPointerMove, onPointerUp };
    el.addEventListener("pointerdown", onPointerDown);
    el.addEventListener("pointermove", onPointerMove);
    el.addEventListener("pointerup", onPointerUp);
    el.addEventListener("pointercancel", onPointerUp);
  },

  unmounted(el) {
    const { onPointerDown, onPointerMove, onPointerUp } = el._dragScroll;
    el.removeEventListener("pointerdown", onPointerDown);
    el.removeEventListener("pointermove", onPointerMove);
    el.removeEventListener("pointerup", onPointerUp);
    el.removeEventListener("pointercancel", onPointerUp);
  },
};

export default dragScrollDirective;
