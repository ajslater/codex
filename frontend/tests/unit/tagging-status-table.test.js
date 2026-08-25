/*
 * Tests for the Tagging tab's live Online Tagging Status table.
 *
 * Behavior locked in here:
 *   - The block hides entirely until a snapshot exists.
 *   - The batch header shows progress and tallies; an active scan shows a
 *     live ETA countdown.
 *   - The sources strip lists sources in priority order with their rate
 *     budget, and a rate-limited source shows a retry countdown.
 *   - There is one status column per selected source, in priority order, so
 *     each comic reads as "which source is in which state"; a source the
 *     session didn't select gets no column at all.
 *   - Per-comic rows overlay "needs review" from the live pending-prompt list,
 *     into the column of the source that prompted.
 *   - The Review button opens the match-review popup (promptDialogOpen).
 *   - A capped list reports "showing N of M".
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import { nf } from "@/components/admin/status-helpers";
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
      {
        pk: 1,
        path: "/c/a.cbz",
        status: "matched",
        sourceStatuses: { metron: "matched", comicvine: "no_match" },
      },
      {
        pk: 2,
        path: "/c/b.cbz",
        status: "in_flight",
        sourceStatuses: { metron: "in_flight" },
      },
      { pk: 3, path: "/c/c.cbz", status: "queued", sourceStatuses: {} },
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
    // No live sustained budget in this snapshot → no daily figures.
    expect(strip).not.toContain("day");
  });

  test("drops the retry countdown once the session is not running", () => {
    // Pausing mid-wait used to strand a future deadline in the frozen
    // snapshot, so the paused table counted down and stuck on "retrying…".
    const snapshot = makeSnapshot({ active: false });
    const { wrapper } = mountTable({ snapshot });
    const strip = wrapper.find(".sourcesStrip");
    expect(strip.text()).not.toContain("retry");
    expect(strip.find(".limited").exists()).toBe(false);
    // The static rate budgets still render.
    expect(strip.text()).toContain("3/min");
  });

  test("shows the live daily budget once Metron reports one", () => {
    const snapshot = makeSnapshot();
    // As delivered by the snapshot once comicbox reads Metron's
    // X-RateLimit-* headers (limit varies by donor tier).
    snapshot.sources[0].sustainedLimit = 25_000;
    snapshot.sources[0].sustainedRemaining = 24_987;
    const { wrapper } = mountTable({ snapshot });
    const strip = wrapper.find(".sourcesStrip").text();
    expect(strip).toContain(`${nf(24_987)}/${nf(25_000)} day`);
    // comicvine reported nothing → its chip keeps only the static rate.
    expect(strip).toContain("3/min");
    expect(strip).not.toContain("3/min day");
  });

  test("overlays needs_review from the live pending-prompt list", () => {
    const pendingPrompts = [{ pk: 3, fingerprint: "fp3", source: "metron" }];
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

  test("shows one column per selected source, in priority order", () => {
    const { wrapper } = mountTable({ snapshot: makeSnapshot() });
    const titles = wrapper.vm.headers.map((h) => h.title);
    expect(titles).toEqual(["Comic", "Metron Cloud", "Comic Vine", ""]);
    const headerText = wrapper.find("thead").text();
    expect(headerText).toContain("Metron Cloud");
    expect(headerText).toContain("Comic Vine");
    // The old single Status/Source pair is gone.
    expect(titles).not.toContain("Status");
    expect(titles).not.toContain("Source");
  });

  test("keeps the source column headers on one line", () => {
    // The Comic column claims all the slack, which would otherwise squeeze
    // "Metron Cloud" onto two lines. Assert against the selector Vuetify's
    // own stylesheet uses, so this fails if the markup ever stops matching
    // it — a class that no rule targets would style nothing.
    const { wrapper } = mountTable({ snapshot: makeSnapshot() });
    const styled = wrapper.element.querySelectorAll(
      ".v-data-table .v-table__wrapper > table > thead > tr th.v-data-table-column--nowrap",
    );
    expect([...styled].map((th) => th.textContent.trim())).toEqual([
      "Metron Cloud",
      "Comic Vine",
    ]);
  });

  test("omits the column of a source this session didn't select", () => {
    const snapshot = makeSnapshot();
    snapshot.batch.sources = ["metron"];
    const { wrapper } = mountTable({ snapshot });
    const titles = wrapper.vm.headers.map((h) => h.title);
    expect(titles).toEqual(["Comic", "Metron Cloud", ""]);
    expect(wrapper.find("thead").text()).not.toContain("Comic Vine");
  });

  test("reads each source's own state per comic", () => {
    const { wrapper } = mountTable({ snapshot: makeSnapshot() });
    const [matched, inFlight, queued] = wrapper.vm.rows;
    // The matched comic: won by metron, nothing from comicvine.
    expect(matched.cells).toEqual({ metron: "matched", comicvine: "no_match" });
    // Being looked up by metron; comicvine's turn hasn't come yet.
    expect(inFlight.cells).toEqual({
      metron: "in_flight",
      comicvine: "queued",
    });
    // Not reached yet, so every column reads as queued.
    expect(queued.cells).toEqual({ metron: "queued", comicvine: "queued" });
    const bodyText = wrapper.find("tbody").text();
    expect(bodyText).toContain("Matched");
    expect(bodyText).toContain("Looking up");
    expect(bodyText).toContain("Queued");
  });

  test("labels a first-wins leftover source Skipped, not an em-dash", () => {
    const snapshot = makeSnapshot({
      comics: [
        {
          pk: 1,
          path: "/c/a.cbz",
          status: "matched",
          sourceStatuses: { metron: "matched" },
        },
      ],
    });
    const { wrapper } = mountTable({ snapshot });
    expect(wrapper.vm.rows[0].cells).toEqual({
      metron: "matched",
      comicvine: "skipped",
    });
    const cell = wrapper.findAll("tbody .statusCell").at(-1);
    expect(cell.text()).toBe("Skipped");
    expect(cell.attributes("title")).toContain("earlier source");
  });

  test("does not claim Skipped under merge-all-sources", () => {
    // Under merge every source runs, so a missing cell is genuinely unknown.
    const snapshot = makeSnapshot({
      comics: [
        {
          pk: 1,
          path: "/c/a.cbz",
          status: "matched",
          sourceStatuses: { metron: "matched" },
        },
      ],
    });
    snapshot.batch.mergeAllSources = true;
    const { wrapper } = mountTable({ snapshot });
    expect(wrapper.vm.rows[0].cells.comicvine).toBe(null);
  });

  test("fills a cell-less no_match row with No match in every column", () => {
    // A silently failed search — or a pre-upgrade snapshot — leaves no cells;
    // the row-level outcome is still the truth for each searched source.
    const snapshot = makeSnapshot({
      comics: [{ pk: 1, path: "/c/a.cbz", status: "no_match" }],
    });
    const { wrapper } = mountTable({ snapshot });
    expect(wrapper.vm.rows[0].cells).toEqual({
      metron: "no_match",
      comicvine: "no_match",
    });
  });

  test("shows Waiting for a source stalled by its rate limit", () => {
    const snapshot = makeSnapshot();
    snapshot.comics[1].sourceStatuses = {
      metron: "matched",
      comicvine: "waiting",
    };
    const { wrapper } = mountTable({ snapshot });
    expect(wrapper.vm.rows[1].cells.comicvine).toBe("waiting");
    expect(wrapper.find("tbody").text()).toContain("Waiting");
  });

  test("marks needs_review only in the column of the source that prompted", () => {
    const pendingPrompts = [{ pk: 1, fingerprint: "fp1", source: "comicvine" }];
    const { wrapper } = mountTable({
      snapshot: makeSnapshot(),
      pendingPrompts,
    });
    const row = wrapper.vm.rows[0];
    expect(row.cells.comicvine).toBe("needs_review");
    // The other source keeps reporting what it actually did.
    expect(row.cells.metron).toBe("matched");
  });

  test("renders a matched pre-upgrade snapshot with an explained em-dash", () => {
    // The tagging cache outlives an upgrade, so a matched row can arrive with
    // no cells at all — there the winning source is unknowable, and the only
    // honest cell is a dash (with a tooltip saying why).
    const snapshot = makeSnapshot({
      comics: [{ pk: 1, path: "/c/a.cbz", status: "matched" }],
    });
    const { wrapper } = mountTable({ snapshot });
    expect(wrapper.vm.rows[0].cells).toEqual({ metron: null, comicvine: null });
    const dash = wrapper.find("tbody .muted");
    expect(dash.text()).toBe("—");
    expect(dash.attributes("title")).toContain("did not report");
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
        {
          pk: 1,
          path: "/c/a.cbz",
          status: "user_matched",
          sourceStatuses: { metron: "user_matched" },
        },
        {
          pk: 2,
          path: "/c/b.cbz",
          status: "user_skipped",
          sourceStatuses: { metron: "user_skipped" },
        },
      ],
    });
    // Comic 2 has drifted back into the live prompt queue.
    const pendingPrompts = [{ pk: 2, fingerprint: "fp2", source: "metron" }];
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

  test("a paused session reads Paused and offers Resume + Cancel", () => {
    const { wrapper } = mountTable({
      snapshot: makeSnapshot({ active: false, resumable: true }),
    });
    expect(wrapper.text()).toContain("Paused");
    expect(wrapper.text()).toContain("Resume");
    // The session isn't finished, so the close action reads "Cancel", not
    // "Dismiss", alongside Resume.
    expect(wrapper.findComponent(ConfirmDialogStub).props().buttonText).toBe(
      "Cancel",
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
      comics: [
        {
          pk: 3,
          path: "/c/c.cbz",
          status: "needs_review",
          sourceStatuses: { metron: "needs_review" },
        },
      ],
    });
    // The daemon hasn't recorded the skip yet, but the local overlay has.
    const { wrapper } = mountTable({
      snapshot,
      pendingPrompts: [],
      locallyResolved: {
        3: { status: "user_skipped", sources: { metron: "user_skipped" } },
      },
    });
    const byPk = Object.fromEntries(
      wrapper.vm.rows.map((r) => [r.pk, r.status]),
    );
    expect(byPk[3]).toBe("user_skipped");
    // The overlay reaches the resolving source's column too, not just the row.
    expect(wrapper.vm.cellStatus(wrapper.vm.rows[0], "metron")).toBe(
      "user_skipped",
    );
  });
});

export default {};
