/*
 * The deprecated Docker Hub image sets ``version.dockerHub`` in the
 * session payload. Admins get a top snackbar telling them to switch to
 * ghcr.io. Dismissing it hides it for a day, per browser; it must come
 * back, because the point is to nag until the image is changed. ghcr.io
 * and native installs never render it at all.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import DockerHubDeprecatedSnackbar from "@/components/docker-hub-deprecated-snackbar.vue";
import vuetify from "@/plugins/vuetify";

const DISMISSED_KEY = "codex-docker-hub-warning-dismissed";
const DOCS_URL =
  "https://codex-comic-reader.readthedocs.io/DOCKER/#migrating-from-docker-hub";
const HOUR_MS = 60 * 60 * 1000;

// Render the snackbar body inline instead of through Vuetify's overlay
// (which needs browser APIs happy-dom lacks).
const VSnackbarStub = {
  name: "VSnackbar",
  props: ["modelValue"],
  template:
    "<div v-if='modelValue' id='snackbar'><slot /><slot name='actions' /></div>",
};

function mountSnackbar({ isStaff = true, version = { dockerHub: true } } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { isStaff }, version },
    },
  });
  return mount(DockerHubDeprecatedSnackbar, {
    global: {
      plugins: [vuetify, pinia],
      stubs: { VSnackbar: VSnackbarStub },
    },
  });
}

describe("DockerHubDeprecatedSnackbar", () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("admins on the docker hub image are told to switch", () => {
    const wrapper = mountSnackbar();

    const snackbar = wrapper.find("#snackbar");
    expect(snackbar.exists()).toBe(true);
    expect(snackbar.text()).toContain("ghcr.io/ajslater/codex");
    expect(wrapper.find(`a[href="${DOCS_URL}"]`).exists()).toBe(true);
  });

  test("non-admins see nothing", () => {
    const wrapper = mountSnackbar({ isStaff: false });

    expect(wrapper.find("#snackbar").exists()).toBe(false);
  });

  test("ghcr.io and native installs see nothing", () => {
    const ghcr = mountSnackbar({ version: { dockerHub: false } });
    expect(ghcr.find("#snackbar").exists()).toBe(false);

    // Before the session payload lands there is no version at all.
    const booting = mountSnackbar({ version: null });
    expect(booting.find("#snackbar").exists()).toBe(false);
  });

  test("dismissing hides it and remembers when", async () => {
    const wrapper = mountSnackbar();

    await wrapper.find("button").trigger("click");

    expect(wrapper.find("#snackbar").exists()).toBe(false);
    const dismissedAt = Number(localStorage.getItem(DISMISSED_KEY));
    expect(Date.now() - dismissedAt).toBeLessThan(HOUR_MS);
  });

  test("a dismissal from earlier today keeps it hidden", () => {
    localStorage.setItem(DISMISSED_KEY, String(Date.now() - HOUR_MS));

    expect(mountSnackbar().find("#snackbar").exists()).toBe(false);
  });

  test("a dismissal from yesterday brings it back", () => {
    localStorage.setItem(DISMISSED_KEY, String(Date.now() - 25 * HOUR_MS));

    expect(mountSnackbar().find("#snackbar").exists()).toBe(true);
  });

  test("blocked storage still shows it", () => {
    vi.stubGlobal("localStorage", {
      getItem() {
        throw new Error("blocked");
      },
      setItem() {
        throw new Error("blocked");
      },
    });

    expect(mountSnackbar().find("#snackbar").exists()).toBe(true);
  });
});
