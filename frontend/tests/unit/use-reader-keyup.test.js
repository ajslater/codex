/*
 * The reader's keyboard shortcuts must not act on keys meant for a dialog or
 * menu over the reader. Vuetify closes an overlay on Escape keydown and
 * focuses its activator, so the Escape keyup lands outside any overlay.
 */
import { createTestingPinia } from "@pinia/testing";
import { shallowMount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { effectScope } from "vue";

import ReaderSettingsScope from "@/components/reader/drawer/reader-settings-scope.vue";
import ReaderToolbarNav from "@/components/reader/toolbars/nav/reader-toolbar-nav.vue";
import ReaderToolbarTop from "@/components/reader/toolbars/top/reader-toolbar-top.vue";
import {
  isInOverlay,
  useReaderKeyUp,
} from "@/components/reader/use-reader-keyup";
import vuetify from "@/plugins/vuetify";

const KEYS = Object.freeze({ ArrowRight: "ArrowRight", Escape: "Escape" });

function press(type, target, code, init = {}) {
  target.dispatchEvent(
    new KeyboardEvent(type, {
      bubbles: true,
      code,
      key: KEYS[code],
      ...init,
    }),
  );
}

function setupDom() {
  document.body.innerHTML = `
    <button id="activator"></button>
    <div class="v-overlay">
      <div class="v-overlay__content"><button id="inOverlay"></button></div>
    </div>`;
  return {
    activator: document.querySelector("#activator"),
    inOverlay: document.querySelector("#inOverlay"),
    overlay: document.querySelector(".v-overlay"),
  };
}

function tap(target, code) {
  press("keydown", target, code);
  press("keyup", target, code);
}

describe("useReaderKeyUp", () => {
  let dom, listener, scope;

  beforeEach(() => {
    dom = setupDom();
    listener = vi.fn();
    scope = effectScope();
    scope.run(() => useReaderKeyUp(listener));
  });

  afterEach(() => {
    scope.stop();
    document.body.replaceChildren();
  });

  test("keys outside an overlay reach the listener", () => {
    tap(document.body, "ArrowRight");
    expect(listener).toHaveBeenCalledOnce();
    expect(listener.mock.calls[0][0].key).toBe("ArrowRight");
  });

  test("keys inside an overlay are ignored", () => {
    tap(dom.inOverlay, "ArrowRight");
    press("keyup", dom.inOverlay, "Escape");
    expect(listener).not.toHaveBeenCalled();
  });

  test("Escape that closes an overlay is ignored after focus leaves it", () => {
    press("keydown", dom.inOverlay, "Escape");
    dom.overlay.remove();
    press("keyup", dom.activator, "Escape");
    expect(listener).not.toHaveBeenCalled();

    // The next Escape is the reader's again.
    tap(dom.activator, "Escape");
    expect(listener).toHaveBeenCalledOnce();
  });

  test("a held key stays with the overlay it was pressed in", () => {
    press("keydown", dom.inOverlay, "Escape");
    press("keydown", dom.activator, "Escape", { repeat: true });
    press("keyup", dom.activator, "Escape");
    expect(listener).not.toHaveBeenCalled();
  });

  test("an overlay that stops keydown still keeps its key", () => {
    dom.inOverlay.addEventListener("keydown", (event) =>
      event.stopPropagation(),
    );
    press("keydown", dom.inOverlay, "Escape");
    press("keyup", dom.activator, "Escape");
    expect(listener).not.toHaveBeenCalled();
  });

  test("stopping the scope removes the listeners", () => {
    scope.stop();
    tap(document.body, "ArrowRight");
    expect(listener).not.toHaveBeenCalled();
  });

  test("targets without closest are outside any overlay", () => {
    expect(isInOverlay(document)).toBe(false);
    expect(isInOverlay(globalThis)).toBe(false);
    expect(isInOverlay(null)).toBe(false);
  });
});

describe.each([
  ["ReaderToolbarTop", ReaderToolbarTop],
  ["ReaderToolbarNav", ReaderToolbarNav],
  ["ReaderSettingsScope", ReaderSettingsScope],
])("%s keyup shortcuts", (_name, component) => {
  let dom, keyUpListener, wrapper;

  beforeEach(() => {
    dom = setupDom();
    keyUpListener = vi.spyOn(component.methods, "_keyUpListener");
    keyUpListener.mockImplementation(() => {});
    wrapper = shallowMount(component, {
      global: { plugins: [createTestingPinia(), vuetify] },
    });
  });

  afterEach(() => {
    wrapper.unmount();
    keyUpListener.mockRestore();
    document.body.replaceChildren();
  });

  test("ignore keys that went to an overlay", () => {
    tap(dom.inOverlay, "ArrowRight");
    press("keydown", dom.inOverlay, "Escape");
    press("keyup", dom.activator, "Escape");
    expect(keyUpListener).not.toHaveBeenCalled();

    tap(document.body, "Escape");
    expect(keyUpListener).toHaveBeenCalledOnce();
  });
});
