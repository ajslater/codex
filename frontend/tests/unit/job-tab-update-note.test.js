/*
 * The Update Codex job says which version it would install.
 *
 * In Docker it can't install anything — the runtime image has no pip —
 * so it points at the image registry instead of promising an upgrade.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import AdminJobsTab from "@/components/admin/tabs/job-tab.vue";
import vuetify from "@/plugins/vuetify";

const GHCR_URL = "https://github.com/ajslater/codex/pkgs/container/codex";

function mountTab({
  installed = "1.0.0",
  latest = "2.0.0",
  outdated = true,
  docker = false,
} = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { isStaff: true } },
      admin: { allLibrarianStatuses: {} },
      common: { versions: { installed, latest, outdated, docker } },
    },
  });
  return mount(AdminJobsTab, {
    global: {
      plugins: [vuetify, pinia],
      mocks: { $route: { hash: "" } },
    },
  });
}

function notes(wrapper) {
  return wrapper.findAll(".jobVersionNote").map((n) => n.text());
}

describe("AdminJobsTab — Update Codex version note", () => {
  test("names the version it would install", () => {
    const wrapper = mountTab();

    expect(notes(wrapper)).toStrictEqual(["Will install codex v2.0.0"]);
  });

  test("says so when there is nothing to install", () => {
    const wrapper = mountTab({ latest: "1.0.0", outdated: false });

    expect(notes(wrapper)[0]).toBe("Codex v1.0.0 is the latest version");
  });

  test("admits when the latest version has not been fetched yet", () => {
    const wrapper = mountTab({ latest: "fetching...", outdated: false });

    expect(notes(wrapper)[0]).toContain("latest version is unknown");
  });

  test("in docker it recommends a new image and links to the registry", () => {
    const wrapper = mountTab({ docker: true });

    const text = notes(wrapper).join(" ");
    expect(text).toContain("Codex v2.0.0 is available");
    expect(text).toContain("pulling a new image");
    const link = wrapper
      .findAll("a")
      .find((a) => a.attributes("href") === GHCR_URL);
    expect(link).toBeTruthy();
  });

  test("the codex software section is anchored for deep links", () => {
    const wrapper = mountTab();

    expect(wrapper.find("#codexSoftware").exists()).toBe(true);
  });
});
