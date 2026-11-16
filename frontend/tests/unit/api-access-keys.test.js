/*
 * The keys section of the API Access dialog.
 *
 * Behavior locked in here:
 *   - The list shows admins what each scope logs in to; only admins can
 *     hold more than one kind worth telling apart. The universal row
 *     explains that it is the old bearer token and cannot come back. An
 *     unused one reads "Not since upgrade": older versions recorded no use.
 *   - Every revoke goes through a confirmation.
 *   - Create is never silently disabled: a blank name is refused on submit
 *     with a visible reason. Only admins pick a kind; everyone else makes a
 *     Device Key.
 *   - The new key's help is one line for OPDS and KOReader alike, offers the
 *     Bearer header only while OPDS is on, and says so when the key would
 *     log in nowhere.
 *   - The section explains that OPDS apps often take a username and
 *     password, and that a Device Key per app is the better password.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ApiKeyCreate from "@/components/api-access/api-key-create.vue";
import ApiKeyList from "@/components/api-access/api-key-list.vue";
import ApiKeyReveal from "@/components/api-access/api-key-reveal.vue";
import ApiKeys from "@/components/api-access/api-keys.vue";
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
const KEYS = Object.freeze([
  Object.freeze({ pk: 1, name: "Kobo", scope: "device", prefix: "abcd" }),
  Object.freeze({
    pk: 2,
    name: "Universal Token",
    scope: "universal",
    prefix: "9f8e",
    lastUsedAt: "2026-11-01T00:00:00Z",
  }),
  Object.freeze({ pk: 3, name: "Grafana", scope: "stats", prefix: "wxyz" }),
]);

function mountWith(component, props) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { username: "alice" } },
      common: { form: { errors: [], fieldErrors: {}, success: "" } },
    },
  });
  const wrapper = mount(component, {
    props,
    global: { plugins: [vuetify, pinia], stubs: { VDialog: VDialogStub } },
  });
  return { wrapper, store: useAuthStore() };
}

describe("ApiKeyList", () => {
  test("shows admins what each scope logs in to", () => {
    const { wrapper } = mountWith(ApiKeyList, {
      apiKeys: KEYS,
      showAccess: true,
    });
    const text = wrapper.text();
    expect(text).toContain("OPDS · KOReader");
    expect(text).toContain("Everything (legacy)");
    expect(text).toContain("Stats");
    expect(text).toContain("abcd…");
    expect(text).toContain("Never");
  });

  test("everyone else gets no Access column", () => {
    const { wrapper } = mountWith(ApiKeyList, { apiKeys: KEYS.slice(0, 2) });
    const headers = wrapper.findAll("thead th").map((th) => th.text());
    expect(headers).toEqual(["Name", "Key", "Last used", ""]);
    expect(wrapper.text()).not.toContain("OPDS · KOReader");
    expect(wrapper.find(".universalHint td").attributes("colspan")).toBe("4");
  });

  test("an unused Universal Token reads not used since the upgrade", () => {
    const { wrapper } = mountWith(ApiKeyList, {
      apiKeys: [{ ...KEYS[1], lastUsedAt: undefined }, KEYS[0]],
    });
    const cells = wrapper.findAll("tbody tr td:nth-child(3)");
    expect(cells.map((cell) => cell.text())).toEqual([
      "Not since upgrade",
      "Never",
    ]);
  });

  test("the universal row says what it is", () => {
    const { wrapper } = mountWith(ApiKeyList, { apiKeys: KEYS });
    const hint = wrapper.find(".universalHint").text();
    expect(hint).toContain("old Authorization Bearer Token");
    expect(hint).toContain("can no longer be shown or made again");
    expect(hint).toContain("Device Keys");
  });

  test("revokes only after Confirm", async () => {
    const { wrapper, store } = mountWith(ApiKeyList, { apiKeys: KEYS });
    const revoke = wrapper.find('button[title="Revoke Universal Token"]');
    await revoke.trigger("click");
    expect(store.deleteApiKey).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("A Universal Token cannot be made again.");
    await wrapper.find(".confirmButton").trigger("click");
    expect(store.deleteApiKey).toHaveBeenCalledExactlyOnceWith(2);
  });

  test("an empty list says so", () => {
    const { wrapper } = mountWith(ApiKeyList, { apiKeys: [] });
    expect(wrapper.text()).toContain("No API keys yet.");
  });
});

describe("ApiKeyCreate", () => {
  test("a blank name is refused on submit, with a reason", async () => {
    const { wrapper, store } = mountWith(ApiKeyCreate, { isAdmin: false });
    const create = wrapper.find('button[type="submit"]');
    expect(create.attributes("disabled")).toBeUndefined();
    await wrapper.find("form").trigger("submit");
    expect(store.createApiKey).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Name the key");
  });

  test("a user makes a Device Key and picks no kind", async () => {
    const { wrapper, store } = mountWith(ApiKeyCreate, { isAdmin: false });
    store.createApiKey.mockResolvedValue("secret");
    expect(wrapper.findComponent({ name: "VSelect" }).exists()).toBe(false);
    await wrapper.find("input").setValue("  Kobo  ");
    await wrapper.find("form").trigger("submit");
    await wrapper.vm.$nextTick();
    expect(store.createApiKey).toHaveBeenCalledWith({
      name: "Kobo",
      scope: "device",
    });
    expect(wrapper.emitted("created")).toEqual([
      [{ key: "secret", name: "Kobo", scope: "device" }],
    ]);
  });

  test("an admin can make a Stats key", async () => {
    const { wrapper, store } = mountWith(ApiKeyCreate, { isAdmin: true });
    store.createApiKey.mockResolvedValue("secret");
    const select = wrapper.findComponent({ name: "VSelect" });
    expect(select.props("items").map((item) => item.value)).toEqual([
      "device",
      "stats",
    ]);
    wrapper.vm.scope = "stats";
    wrapper.vm.name = "Grafana";
    await wrapper.find("form").trigger("submit");
    expect(store.createApiKey).toHaveBeenCalledWith({
      name: "Grafana",
      scope: "stats",
    });
  });
});

describe("ApiKeyReveal", () => {
  const BASE = Object.freeze({
    apiKey: "abcdsecretkey",
    name: "Kobo",
    username: "alice",
  });

  test("a device key gets one line for OPDS and KOReader alike", () => {
    const { wrapper } = mountWith(ApiKeyReveal, {
      ...BASE,
      scope: "device",
      urls: { opdsV1: "/opds/v1.2/", koreader: "/koreader" },
    });
    expect(wrapper.text()).toContain("shown only this once");
    const usage = wrapper.findAll(".usage");
    expect(usage).toHaveLength(1);
    const text = usage[0].text();
    expect(text).toContain("username alice and this key as the password");
    expect(text).toContain("Authorization: Bearer abcdsecretkey");
    expect(text).not.toContain("OPDS");
    expect(text).not.toContain("KOReader");
    expect(wrapper.find(".apiKeyNote").exists()).toBe(false);
  });

  test("with only KOReader on, no header is offered", () => {
    const { wrapper } = mountWith(ApiKeyReveal, {
      ...BASE,
      scope: "device",
      urls: { koreader: "/koreader" },
    });
    const text = wrapper.find(".usage").text();
    expect(text).toContain("this key as the password");
    expect(text).not.toContain("Authorization");
  });

  test("a device key with no reader API on says so", () => {
    const { wrapper } = mountWith(ApiKeyReveal, {
      ...BASE,
      scope: "device",
      urls: {},
    });
    expect(wrapper.find(".apiKeyNote").text()).toContain(
      "No reader API is turned on",
    );
  });

  test("a stats key shows the ?apiKey= URL and the Bearer header", () => {
    const { wrapper } = mountWith(ApiKeyReveal, {
      ...BASE,
      scope: "stats",
      urls: { stats: "/api/v4/admin/stats" },
    });
    const text = wrapper.text();
    expect(text).toContain("/api/v4/admin/stats?apiKey=abcdsecretkey");
    expect(text).toContain("Authorization: Bearer abcdsecretkey");
    expect(wrapper.find(".apiKeyNote").exists()).toBe(false);
  });

  test("a stats key made while Stats API Keys is off says so", () => {
    const { wrapper } = mountWith(ApiKeyReveal, {
      ...BASE,
      scope: "stats",
      urls: {},
    });
    expect(wrapper.find(".apiKeyNote").text()).toContain(
      "Stats API Keys is turned off",
    );
  });
});

describe("ApiKeys", () => {
  test("only admins see the Access column", async () => {
    const { wrapper, store } = mountWith(ApiKeys, { urls: {} });
    store.apiKeys = [KEYS[0]];
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).not.toContain("Access");
    store.user = { username: "alice", isStaff: true };
    await wrapper.vm.$nextTick();
    expect(wrapper.find("thead").text()).toContain("Access");
  });

  test("prefers a Device Key per app over the account password for OPDS", () => {
    const { wrapper } = mountWith(ApiKeys, { urls: {} });
    const text = wrapper.text();
    expect(text).toContain("username and password");
    expect(text).toContain("use a Device Key as its password instead");
  });
});
