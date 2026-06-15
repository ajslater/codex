/*
 * Tests for the Tagging tab's live Online Tagging Status table.
 *
 * Behavior locked in here:
 *   - The block hides entirely until a snapshot exists.
 *   - The batch header shows progress and tallies; an active scan shows a
 *     live ETA countdown.
 *   - The sources strip lists sources in priority order with their rate
 *     budget, and a rate-limited source shows a retry countdown.
 *   - Per-comic rows overlay "needs review" from the live pending-prompt list.
 *   - The Review button opens the match-review popup (promptDialogOpen).
 *   - A capped list reports "showing N of M".
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import TaggingStatusTable from "@/components/admin/tabs/tagging-status-table.vue";
import vuetify from "@/plugins/vuetify";
import { useOnlineTagStore } from "@/stores/online-tag";

const ConfirmDialogStub = {
  name: "ConfirmDialog",
  props: ["buttonText"],
  emits: ["confirm"],
  render: () => null,
};

const SECONDS = 1000;

function makeSnapshot(overrides = {}) {
  const nowSecs = Date.now() / SECONDS;
  return {
    sessionId: "sid-1",
    active: true,
    batch: {
      total: 10,
      completed: 4,
      matched: 3,
      needsReview: 1,
      noMatch: 1,
      error: 0,
      queued: 6,
      sources: ["metron", "comicvine"],
      matchMode: "auto",
      mergeAllSources: false,
      etaEpoch: nowSecs + 120,
    },
    sources: [
      {
        source: "metron",
        ratePerMinute: 20,
        rateLimited: false,
        retryAtEpoch: null,
      },
      {
        source: "comicvine",
        ratePerMinute: 3,
        rateLimited: true,
        retryAtEpoch: nowSecs + 30,
      },
    ],
    comics: [
      { pk: 1, path: "/c/a.cbz", status: "matched", wonSource: "metron" },
      { pk: 2, path: "/c/b.cbz", status: "in_flight", wonSource: null },
      { pk: 3, path: "/c/c.cbz", status: "queued", wonSource: null },
    ],
    comicCount: 10,
    shownCount: 3,
    ...overrides,
  };
}

function mountTable({
  snapshot = null,
  pendingPrompts = [],
  locallyResolved = {},
} = {}) {
  const pinia = createTestingPinia({
    initialState: {
      onlineTag: {
        snapshot,
        pendingPrompts,
        promptDialogOpen: false,
        locallyResolved,
      },
    },
  });
  const wrapper = mount(TaggingStatusTable, {
    global: {
      plugins: [pinia, vuetify],
      stubs: { ConfirmDialog: ConfirmDialogStub },
    },
  });
  return { wrapper, store: useOnlineTagStore() };
}

describe("AdminTaggingStatusTable", () => {
  test("renders nothing until a snapshot exists", () => {
    const { wrapper } = mountTable({ snapshot: null });
    expect(wrapper.text()).toBe("");
  });

  test("shows batch progress, tallies, and a live ETA when active", () => {
    const { wrapper } = mountTable({ snapshot: makeSnapshot() });
    const text = wrapper.text();
    expect(text).toContain("Tagging");
    expect(text).toContain("4 / 10");
    expect(text).toContain("3 matched");
    expect(text).toContain("need review");
    expect(text).toContain("left"); // ETA countdown
  });

  test("reads Finished and drops the ETA once the scan is inactive", () => {
    const snapshot = makeSnapshot({ active: false });
    const { wrapper } = mountTable({ snapshot });
    const text = wrapper.text();
    expect(text).toContain("Finished");
    expect(text).not.toContain("left");
  });

  test("lists sources in order with rate budgets and a retry countdown", () => {
    const { wrapper } = mountTable({ snapshot: makeSnapshot() });
    const strip = wrapper.find(".sourcesStrip").text();
    expect(strip).toContain("Metron Cloud");
    expect(strip).toContain("20/min");
    expect(strip).toContain("Comic Vine");
    expect(strip).toContain("3/min");
    // comicvine is rate-limited → a retry countdown is shown.
    expect(strip).toContain("retry");
  });

  test("overlays needs_review from the live pending-prompt list", () => {
    const pendingPrompts = [{ pk: 3, fingerprint: "fp3" }];
    const { wrapper } = mountTable({
      snapshot: makeSnapshot(),
      pendingPrompts,
    });
    const byPk = Object.fromEntries(
      wrapper.vm.rows.map((r) => [r.pk, r.status]),
    );
    // Comic 3 was "queued" in the snapshot but has a live prompt now.
    expect(byPk[3]).toBe("needs_review");
    expect(byPk[1]).toBe("matched");
    // Live prompt count drives the review tally.
    expect(wrapper.vm.reviewCount).toBe(1);
  });

  test("Review opens the match-review popup", () => {
    const { wrapper, store } = mountTable({ snapshot: makeSnapshot() });
    wrapper.vm.openReview();
    expect(store.promptDialogOpen).toBe(true);
  });

  test("reports showing N of M when the list is capped", () => {
    const snapshot = makeSnapshot({ comicCount: 1200, shownCount: 500 });
    const { wrapper } = mountTable({ snapshot });
    expect(wrapper.text()).toContain("Showing 500 of 1,200");
  });

  test("labels admin-resolved outcomes as user matched / skipped", () => {
    const { wrapper } = mountTable({ snapshot: makeSnapshot() });
    expect(wrapper.vm.statusLabel("user_matched")).toBe("User matched");
    expect(wrapper.vm.statusLabel("user_skipped")).toBe("User skipped");
  });

  test("keeps a server-resolved status unless the comic is still pending", () => {
    const snapshot = makeSnapshot({
      comics: [
        { pk: 1, path: "/c/a.cbz", status: "user_matched", wonSource: null },
        { pk: 2, path: "/c/b.cbz", status: "user_skipped", wonSource: null },
      ],
    });
    // Comic 2 has drifted back into the live prompt queue.
    const pendingPrompts = [{ pk: 2, fingerprint: "fp2" }];
    const { wrapper } = mountTable({ snapshot, pendingPrompts });
    const byPk = Object.fromEntries(
      wrapper.vm.rows.map((r) => [r.pk, r.status]),
    );
    expect(byPk[1]).toBe("user_matched"); // recorded outcome stands
    expect(byPk[2]).toBe("needs_review"); // live prompt overrides
  });

  test("offers a Pause control while active, Dismiss when finished", () => {
    const active = mountTable({ snapshot: makeSnapshot({ active: true }) });
    const pauseDialog = active.wrapper.findComponent(ConfirmDialogStub);
    expect(pauseDialog.props().buttonText).toBe("Pause");

    const finished = mountTable({
      snapshot: makeSnapshot({ active: false, resumable: false }),
    });
    expect(finished.wrapper.text()).toContain("Finished");
    expect(
      finished.wrapper.findComponent(ConfirmDialogStub).props().buttonText,
    ).toBe("Dismiss");
  });

  test("a paused session reads Paused and offers Resume + Dismiss", () => {
    const { wrapper } = mountTable({
      snapshot: makeSnapshot({ active: false, resumable: true }),
    });
    expect(wrapper.text()).toContain("Paused");
    expect(wrapper.text()).toContain("Resume");
    // Dismiss is still available alongside Resume.
    expect(wrapper.findComponent(ConfirmDialogStub).props().buttonText).toBe(
      "Dismiss",
    );
  });

  test("confirming pause calls pauseSession and shows a pausing state", async () => {
    const { wrapper, store } = mountTable({ snapshot: makeSnapshot() });
    wrapper.findComponent(ConfirmDialogStub).vm.$emit("confirm");
    await wrapper.vm.$nextTick();
    expect(store.pauseSession).toHaveBeenCalled();
    expect(wrapper.vm.pausing).toBe(true);
  });

  test("resume calls resumeSession and shows a resuming state", async () => {
    const { wrapper, store } = mountTable({
      snapshot: makeSnapshot({ active: false, resumable: true }),
    });
    wrapper.vm.confirmResume();
    await wrapper.vm.$nextTick();
    expect(store.resumeSession).toHaveBeenCalled();
    expect(wrapper.vm.resuming).toBe(true);
  });

  test("dismiss calls dismissSession", () => {
    const { wrapper, store } = mountTable({
      snapshot: makeSnapshot({ active: false, resumable: false }),
    });
    wrapper.vm.confirmDismiss();
    expect(store.dismissSession).toHaveBeenCalled();
  });

  test("clears the pausing state once the session ends", async () => {
    const { wrapper, store } = mountTable({ snapshot: makeSnapshot() });
    wrapper.vm.pausing = true;
    store.snapshot = { ...store.snapshot, active: false };
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.pausing).toBe(false);
  });

  test("clears the resuming state once the scan becomes active", async () => {
    const { wrapper, store } = mountTable({
      snapshot: makeSnapshot({ active: false, resumable: true }),
    });
    wrapper.vm.resuming = true;
    store.snapshot = { ...store.snapshot, active: true };
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.resuming).toBe(false);
  });

  test("applies the optimistic local overlay over a lagging snapshot", () => {
    const snapshot = makeSnapshot({
      comics: [{ pk: 3, path: "/c/c.cbz", status: "needs_review" }],
    });
    // The daemon hasn't recorded the skip yet, but the local overlay has.
    const { wrapper } = mountTable({
      snapshot,
      pendingPrompts: [],
      locallyResolved: { 3: "user_skipped" },
    });
    const byPk = Object.fromEntries(
      wrapper.vm.rows.map((r) => [r.pk, r.status]),
    );
    expect(byPk[3]).toBe("user_skipped");
  });
});

export default {};
