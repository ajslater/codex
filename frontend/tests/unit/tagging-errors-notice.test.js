/*
 * A refused tagging request says why, in the notice snackbar.
 *
 * These caught errors with ``setErrors``, which fills ``form.errors``, and
 * nothing on the Tagging tab, the launcher or the status table renders that:
 * a refused scan or Resume just stopped spinning.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import TaggingStatusTable from "@/components/admin/tabs/tagging-status-table.vue";
import OnlineTagLauncherDialog from "@/components/online-tag/launcher-dialog.vue";
import vuetify from "@/plugins/vuetify";
import { useAdminStore } from "@/stores/admin";
import { useCommonStore } from "@/stores/common";
import { useOnlineTagStore } from "@/stores/online-tag";

const REFUSED = Object.freeze({
  response: { status: 400, data: { detail: "No Comic Vine key." } },
});
const VDialogStub = { name: "VDialog", template: "<div><slot /></div>" };
const ConfirmDialogStub = { name: "ConfirmDialog", render: () => null };

describe("a refused tagging request", () => {
  test("a refused scan start shows its reason", async () => {
    const pinia = createTestingPinia();
    const wrapper = mount(OnlineTagLauncherDialog, {
      props: { book: { collection: "comics", pk: 7, ids: [7] } },
      global: {
        plugins: [vuetify, pinia],
        stubs: { VDialog: VDialogStub, RouterLink: true },
      },
    });
    useAdminStore().taggingDefaults = { configuredSources: ["metron"] };
    useOnlineTagStore().startSession.mockRejectedValue(REFUSED);
    wrapper.vm.sources = ["metron"];
    await wrapper.vm.$nextTick();
    await wrapper.vm.submit();
    expect(useCommonStore().setErrorNotice).toHaveBeenCalledWith(REFUSED);
  });

  test("a refused Resume and Pause show their reasons", async () => {
    const pinia = createTestingPinia();
    const wrapper = mount(TaggingStatusTable, {
      global: {
        plugins: [pinia, vuetify],
        stubs: { ConfirmDialog: ConfirmDialogStub },
      },
    });
    const store = useOnlineTagStore();
    store.resumeSession.mockRejectedValue(REFUSED);
    store.pauseSession.mockRejectedValue(REFUSED);
    await wrapper.vm.confirmResume();
    await wrapper.vm.confirmPause();
    expect(useCommonStore().setErrorNotice).toHaveBeenCalledTimes(2);
  });
});
