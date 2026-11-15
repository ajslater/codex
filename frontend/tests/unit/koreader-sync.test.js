/*
 * The profile dialog's KOReader Sync panel.
 *
 * It shows only while the KOReader Sync admin flag is on, and its server URL
 * is the origin plus the URL path prefix plus /koreader, which is what the
 * user types into KOReader's custom sync server setting.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import ProfileDialog from "@/components/auth/profile-dialog.vue";
import vuetify from "@/plugins/vuetify";

function mountDialog(koreaderSync) {
  const pinia = createTestingPinia({
    initialState: {
      auth: {
        user: { username: "alice", email: "" },
        adminFlags: { emailEnabled: true, koreaderSync },
        MIN_PASSWORD_LENGTH: 4,
      },
    },
  });
  return mount(ProfileDialog, {
    global: {
      plugins: [vuetify, pinia],
      stubs: {
        CodexListItem: true,
        SubmitFooter: true,
        CloseButton: true,
        KOReaderSync: true,
      },
    },
  });
}

describe("KOReader Sync panel visibility", () => {
  test("hidden while the flag is off", () => {
    const vm = mountDialog(false).vm;
    expect(vm.koreaderSync).toBe(false);
  });

  test("shown while the flag is on", () => {
    const vm = mountDialog(true).vm;
    expect(vm.koreaderSync).toBe(true);
  });
});

describe("KOReader Sync server URL", () => {
  let savedCodex;

  beforeEach(() => {
    savedCodex = globalThis.CODEX;
    vi.resetModules();
  });

  afterEach(() => {
    globalThis.CODEX = savedCodex;
  });

  test("carries the URL path prefix", async () => {
    globalThis.CODEX = { APP_PATH: "/codex/" };
    const { default: KOReaderSync } =
      await import("@/components/auth/koreader-sync.vue");
    const wrapper = mount(KOReaderSync, {
      props: { username: "alice" },
      global: { plugins: [vuetify] },
    });
    expect(wrapper.vm.serverURL).toBe(`${location.origin}/codex/koreader`);
  });

  test("at the server root", async () => {
    globalThis.CODEX = { APP_PATH: "/" };
    const { default: KOReaderSync } =
      await import("@/components/auth/koreader-sync.vue");
    const wrapper = mount(KOReaderSync, {
      props: { username: "alice" },
      global: { plugins: [vuetify] },
    });
    expect(wrapper.vm.serverURL).toBe(`${location.origin}/koreader`);
  });
});
