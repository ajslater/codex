/*
 * The API Access dialog: the one place for OPDS, KOReader and API keys.
 *
 * Behavior locked in here:
 *   - Every open reloads the API URLs (no cache), and the keys for a user.
 *   - An anonymous Non Users visitor sees the URLs and no keys section.
 *   - Each URL is the origin plus its path; an API that is off is absent,
 *     and with none on the dialog says so.
 *   - KOReader's setup help, in KOReader's own menu words, follows its URL,
 *     collapsed until opened: most people never need it.
 *   - The OPDS v2.0 note links to Stump and Readest, off site, without
 *     parentheses.
 *   - URLs and keys are separate sections, and each URL shares one block
 *     with its note or setup help.
 *   - A failed load offers Retry; a pending one shows a sized placeholder.
 *   - Profile's "API Access" button opens it.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ApiAccessDialog from "@/components/api-access/api-access-dialog.vue";
import ProfileDialog from "@/components/auth/profile-dialog.vue";
import vuetify from "@/plugins/vuetify";
import { useAuthStore } from "@/stores/auth";

const VDialogStub = Object.freeze({
  name: "VDialog",
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: `<div class="dialogStub">
    <slot name="activator" :props="{ onClick: () => $emit('update:modelValue', true) }" />
    <slot v-if="modelValue" />
  </div>`,
});
const URLS = Object.freeze({
  opdsV1: "/opds/v1.2/",
  opdsV2: "/opds/v2.0/",
  koreader: "/koreader",
});

function mountDialog(auth = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: {
        user: { username: "alice" },
        apiUrls: URLS,
        apiUrlsError: "",
        apiKeys: [],
        showApiAccessDialog: false,
        ...auth,
      },
    },
  });
  const wrapper = mount(ApiAccessDialog, {
    global: {
      plugins: [vuetify, pinia],
      stubs: { VDialog: VDialogStub, ApiKeys: true },
    },
  });
  return { wrapper, store: useAuthStore() };
}

async function open(wrapper, store) {
  store.showApiAccessDialog = true;
  await wrapper.vm.$nextTick();
}

describe("API Access dialog", () => {
  test("every open reloads the URLs and the keys", async () => {
    const { wrapper, store } = mountDialog();
    await open(wrapper, store);
    store.showApiAccessDialog = false;
    await wrapper.vm.$nextTick();
    await open(wrapper, store);
    expect(store.loadApiUrls).toHaveBeenCalledTimes(2);
    expect(store.loadApiKeys).toHaveBeenCalledTimes(2);
  });

  test("shows each URL as the origin plus its path", async () => {
    const { wrapper, store } = mountDialog();
    await open(wrapper, store);
    const text = wrapper.text();
    const origin = location.origin;
    expect(text).toContain(`${origin}/opds/v1.2/`);
    expect(text).toContain(`${origin}/opds/v2.0/`);
    expect(text).toContain(`${origin}/koreader`);
    expect(text).not.toContain("Stats API");
  });

  test("KOReader help is collapsed until opened", async () => {
    const { wrapper, store } = mountDialog();
    await open(wrapper, store);
    expect(wrapper.text()).toContain("KOReader setup");
    expect(wrapper.text()).not.toContain("Progress sync");
  });

  test("KOReader help uses KOReader's own menu words", async () => {
    const { wrapper, store } = mountDialog();
    await open(wrapper, store);
    await wrapper.find(".v-expansion-panel-title").trigger("click");
    await flushPromises();
    const text = wrapper.text();
    for (const words of [
      "Progress sync",
      "Custom sync server",
      "Register / Login",
      "Document matching method",
      "Binary",
      "Filename",
    ]) {
      expect(text).toContain(words);
    }
    expect(text).toContain("alice");
  });

  test("no KOReader help without the KOReader URL", async () => {
    const { wrapper, store } = mountDialog({
      apiUrls: { opdsV1: "/opds/v1.2/" },
    });
    await open(wrapper, store);
    expect(wrapper.text()).not.toContain("KOReader setup");
  });

  test("URLs and keys are separate sections", async () => {
    const { wrapper, store } = mountDialog();
    await open(wrapper, store);
    expect(wrapper.find(".apiUrlsSection h3").text()).toBe("API URLs");
    // Keys follow the URLs, past a divider.
    const section = wrapper.find(".apiUrlsSection").element;
    const keys = wrapper.findComponent({ name: "ApiKeys" }).element;
    expect(section.nextElementSibling.classList).toContain("v-divider");
    expect(section.nextElementSibling.nextElementSibling).toBe(keys);
  });

  test("each URL shares a block with what explains it", async () => {
    const { wrapper, store } = mountDialog();
    await open(wrapper, store);
    const blocks = wrapper.findAll(".apiUrlBlock");
    expect(blocks).toHaveLength(3);
    for (const [index, title] of [
      "OPDS v1.2",
      "OPDS v2.0",
      "KOReader Sync",
    ].entries()) {
      expect(blocks[index].find(".clipboardTitle").text()).toContain(title);
    }
    expect(blocks[1].find(".apiUrlNote").text()).toContain("Stump");
    expect(blocks[2].text()).toContain("KOReader setup");
    expect(blocks[2].find(".apiUrlNote").exists()).toBe(false);
  });

  test("the OPDS v2.0 note links to Stump and Readest off site", async () => {
    const { wrapper, store } = mountDialog();
    await open(wrapper, store);
    const note = wrapper.find(".apiUrlNote");
    expect(note.text()).toContain(
      "Supported in newer clients such as Stump and Readest.",
    );
    expect(note.text()).not.toContain("(");
    expect(note.text()).not.toContain(")");
    const links = note.findAll("a");
    expect(links.map((link) => link.attributes("href"))).toStrictEqual([
      "https://www.stumpapp.dev/",
      "https://readest.com/",
    ]);
    for (const link of links) {
      expect(link.attributes("target")).toBe("_blank");
      expect(link.findComponent({ name: "VIcon" }).exists()).toBe(true);
    }
  });

  test("an anonymous visitor sees URLs and no keys", async () => {
    const { wrapper, store } = mountDialog({ user: undefined });
    await open(wrapper, store);
    expect(store.loadApiUrls).toHaveBeenCalledOnce();
    expect(store.loadApiKeys).not.toHaveBeenCalled();
    expect(wrapper.findComponent({ name: "ApiKeys" }).exists()).toBe(false);
    expect(wrapper.text()).toContain("/opds/v2.0/");
  });

  test("says so when no API is on", async () => {
    const { wrapper, store } = mountDialog({ apiUrls: {} });
    await open(wrapper, store);
    expect(wrapper.text()).toContain("No APIs are turned on for this server.");
  });

  test("a failed load offers Retry", async () => {
    const { wrapper, store } = mountDialog({
      apiUrls: undefined,
      apiUrlsError: "Could not load the API URLs.",
    });
    await open(wrapper, store);
    expect(wrapper.text()).toContain("Could not load the API URLs.");
    const retry = wrapper
      .findAll("button")
      .find((button) => button.text() === "Retry");
    await retry.trigger("click");
    expect(store.loadApiUrls).toHaveBeenCalledTimes(2);
  });

  test("a pending load shows the placeholder", async () => {
    const { wrapper, store } = mountDialog({ apiUrls: undefined });
    await open(wrapper, store);
    expect(wrapper.find(".apiAccessLoading").exists()).toBe(true);
  });
});

describe("Profile opens API Access", () => {
  test("the API Access button sets the store flag", async () => {
    const pinia = createTestingPinia({
      initialState: {
        auth: {
          user: { username: "alice", email: "" },
          adminFlags: { emailEnabled: true },
          showProfileDialog: true,
        },
      },
    });
    const wrapper = mount(ProfileDialog, {
      global: {
        plugins: [vuetify, pinia],
        stubs: {
          VDialog: VDialogStub,
          CodexListItem: true,
          SubmitFooter: true,
          CloseButton: true,
        },
      },
    });
    const store = useAuthStore();
    const button = wrapper
      .findAll("button")
      .find((candidate) => candidate.text() === "API Access");
    await button.trigger("click");
    expect(store.showApiAccessDialog).toBe(true);
    // The old in-Profile key and KOReader panels are gone.
    expect(wrapper.text()).not.toContain("Device Keys");
    expect(wrapper.text()).not.toContain("KOReader Sync");
  });
});
