/*
 * Tests for the online-tag store's match-review reconciliation.
 *
 * The daemon removes an answered prompt from its cache only when it gets a
 * turn (a busy scan defers that to between comics), so a re-fetch can briefly
 * resurrect a prompt the admin just answered — which flashed stale entries
 * into the match-review dialog. The store suppresses recently-resolved
 * fingerprints until the backend stops echoing them, while letting a drifted
 * re-queue (a *new* fingerprint) through.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/v4/base", () => ({
  HTTP: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

import { HTTP } from "@/api/v4/base";
import { useOnlineTagStore } from "@/stores/online-tag";

const fps = (store) => store.pendingPrompts.map((p) => p.fingerprint);
const promptsResponse = (...fingerprints) => ({
  data: { prompts: fingerprints.map((fingerprint) => ({ fingerprint })) },
});

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe("useOnlineTagStore — resolution reconciliation", () => {
  it("does not resurrect a just-answered prompt that the backend still echoes", async () => {
    const store = useOnlineTagStore();
    store.pendingPrompts = [{ fingerprint: "a" }, { fingerprint: "b" }];
    HTTP.post.mockResolvedValue({});

    await store.resolvePrompt("a", "skip", null, null);
    expect(fps(store)).toEqual(["b"]);
    expect(store.recentlyResolved).toContain("a");

    // Backend lagging: still returns the resolved prompt.
    HTTP.get.mockResolvedValue(promptsResponse("a", "b"));
    await store.loadPrompts({ autoOpen: false });
    expect(fps(store)).toEqual(["b"]); // "a" stays suppressed
    expect(store.recentlyResolved).toEqual(["a"]); // still echoed → kept

    // Backend catches up and drops it.
    HTTP.get.mockResolvedValue(promptsResponse("b"));
    await store.loadPrompts({ autoOpen: false });
    expect(fps(store)).toEqual(["b"]);
    expect(store.recentlyResolved).toEqual([]); // gone → forgotten
  });

  it("lets a drifted re-queue under a new fingerprint through", async () => {
    const store = useOnlineTagStore();
    store.pendingPrompts = [{ fingerprint: "a" }];
    HTTP.post.mockResolvedValue({});
    await store.resolvePrompt("a", "choose", 0, null);

    // The match drifted; the daemon re-queued a fresh prompt as "a2".
    HTTP.get.mockResolvedValue(promptsResponse("a2"));
    await store.loadPrompts({ autoOpen: false });
    expect(fps(store)).toEqual(["a2"]);
  });

  it("remembers every fingerprint when skipping all", async () => {
    const store = useOnlineTagStore();
    store.pendingPrompts = [{ fingerprint: "x" }, { fingerprint: "y" }];
    store.promptDialogOpen = true;
    HTTP.post.mockResolvedValue({});

    await store.skipAllPrompts();
    expect(store.pendingPrompts).toEqual([]);
    expect(store.promptDialogOpen).toBe(false);
    expect(store.recentlyResolved).toEqual(expect.arrayContaining(["x", "y"]));

    // A lagging echo of both is fully suppressed.
    HTTP.get.mockResolvedValue(promptsResponse("x", "y"));
    await store.loadPrompts({ autoOpen: false });
    expect(fps(store)).toEqual([]);
  });

  it("stores the snapshot from loadSnapshot", async () => {
    const store = useOnlineTagStore();
    HTTP.get.mockResolvedValue({ data: { snapshot: { active: true } } });
    await store.loadSnapshot();
    expect(store.snapshot).toEqual({ active: true });
  });

  it("pauses using the snapshot session id when no active session is tracked", async () => {
    const store = useOnlineTagStore();
    store.activeSessionId = null;
    store.snapshot = { sessionId: "sid-9", active: true };
    HTTP.delete.mockResolvedValue({});

    await store.pauseSession();
    expect(HTTP.delete).toHaveBeenCalledWith("/admin/tag-sessions/sid-9");
    expect(store.activeSessionId).toBe(null);
  });

  it("resumes by posting to the resume endpoint and tracks the new session", async () => {
    const store = useOnlineTagStore();
    HTTP.post.mockResolvedValue({
      data: { sessionId: "sid-new", comicCount: 12 },
    });

    const result = await store.resumeSession();
    expect(HTTP.post).toHaveBeenCalledWith("/admin/tag-sessions/resume");
    expect(store.activeSessionId).toBe("sid-new");
    expect(result.comicCount).toBe(12);
  });

  it("dismisses by posting and clearing local snapshot state", async () => {
    const store = useOnlineTagStore();
    store.snapshot = { active: false, resumable: true };
    store.activeSessionId = "sid-1";
    HTTP.post.mockResolvedValue({});

    await store.dismissSession();
    expect(HTTP.post).toHaveBeenCalledWith("/admin/tag-sessions/dismiss");
    expect(store.snapshot).toBe(null);
    expect(store.activeSessionId).toBe(null);
  });

  it("optimistically overlays a resolution and prunes once the server agrees", async () => {
    const store = useOnlineTagStore();
    store.pendingPrompts = [{ fingerprint: "a", pk: 7 }];
    HTTP.post.mockResolvedValue({});

    await store.resolvePrompt("a", "skip", null, null);
    // Table sees the outcome immediately, before any daemon round-trip.
    expect(store.locallyResolved).toEqual({ 7: "user_skipped" });

    // Snapshot still lagging (comic 7 frozen as needs_review) → overlay kept.
    HTTP.get.mockResolvedValue({
      data: { snapshot: { comics: [{ pk: 7, status: "needs_review" }] } },
    });
    await store.loadSnapshot();
    expect(store.locallyResolved).toEqual({ 7: "user_skipped" });

    // Daemon caught up: server now reports user_skipped → overlay pruned.
    HTTP.get.mockResolvedValue({
      data: { snapshot: { comics: [{ pk: 7, status: "user_skipped" }] } },
    });
    await store.loadSnapshot();
    expect(store.locallyResolved).toEqual({});
  });
});

export default {};
