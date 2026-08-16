/*
 * The settings drawer's upgrade call to action.
 *
 * It links to the admin jobs tab, where the Update Codex job lives, so
 * only admins see it — except in Docker, where codex can't install over
 * itself and the upgrade is a new image from the registry. Whether a
 * newer version exists is decided by the server and arrives as
 * ``versions.outdated``; the component used to compare versions itself
 * and got it wrong in two different ways.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import VersionFooter from "@/components/settings/version-footer.vue";
import vuetify from "@/plugins/vuetify";

const GHCR_URL = "https://github.com/ajslater/codex/pkgs/container/codex";

// Captures ``to`` so the deep link target can be asserted.
const RouterLinkStub = {
  name: "RouterLink",
  props: ["to"],
  template: "<a :id='$attrs.id' :title='$attrs.title'><slot /></a>",
};

function mountFooter({ isStaff = true, outdated = true, docker = false } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user: { isStaff } },
      common: {
        versions: {
          installed: "1.0.0",
          latest: "2.0.0",
          outdated,
          docker,
          warning: "",
        },
      },
    },
  });
  return mount(VersionFooter, {
    global: {
      plugins: [vuetify, pinia],
      stubs: { RouterLink: RouterLinkStub },
    },
  });
}

describe("VersionFooter", () => {
  test("admins get a link to the update job", () => {
    const wrapper = mountFooter();

    const link = wrapper.findComponent(RouterLinkStub);
    expect(link.exists()).toBe(true);
    expect(link.props("to")).toStrictEqual({
      name: "admin-jobs",
      hash: "#codexSoftware",
    });
    expect(link.text()).toContain("upgrade to codex v2.0.0");
    expect(link.attributes("title")).toBe("Upgrade Codex");
  });

  test("in docker the link goes to the image registry instead", () => {
    const wrapper = mountFooter({ docker: true });

    expect(wrapper.findComponent(RouterLinkStub).exists()).toBe(false);
    const link = wrapper.find("#latest");
    expect(link.attributes("href")).toBe(GHCR_URL);
    expect(link.attributes("title")).toBe("Docker image repo");
    expect(link.text()).toContain("upgrade to codex v2.0.0");
  });

  test("no announcement for non-admins", () => {
    const wrapper = mountFooter({ isStaff: false });

    expect(wrapper.find("#latest").exists()).toBe(false);
  });

  test("no announcement when up to date", () => {
    const wrapper = mountFooter({ outdated: false });

    expect(wrapper.find("#latest").exists()).toBe(false);
  });

  test("the installed version links to the source", () => {
    const wrapper = mountFooter({ outdated: false });

    const version = wrapper.find("#version");
    expect(version.text()).toContain("codex v1.0.0");
    expect(version.attributes("title")).toBe("Codex source code");
  });
});
