/*
 * Regression: the v4 API client must honor the URL path prefix
 * (server.url_path_prefix), e.g. "/codex" behind a reverse proxy.
 *
 * The bases used to be hardcoded to "/api/v4/" and "/api/v4/ws", so under a
 * subpath every API call 404'd and the websocket hit Channels' outermost
 * URLRouter with a path that didn't start with root_path, raising
 * "No route found for path '/api/v4/ws'." (GitHub #784). They now derive
 * from window.CODEX.APP_PATH, which Django injects with the prefix.
 *
 * Modules read the global at import time, so each case resets the module
 * registry and re-imports after setting CODEX.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

let savedCodex;

beforeEach(() => {
  savedCodex = globalThis.CODEX;
  vi.resetModules();
});

afterEach(() => {
  globalThis.CODEX = savedCodex;
});

describe("v4 base honors the URL path prefix", () => {
  test("under a /codex subpath", async () => {
    globalThis.CODEX = { APP_PATH: "/codex/" };
    const { APP_BASE, V4_BASE } = await import("@/api/v4/base");
    const { WS_URL_V4 } = await import("@/api/v4/notify");

    expect(APP_BASE).toBe("/codex/");
    expect(V4_BASE).toBe("/codex/api/v4/");
    expect(WS_URL_V4).toMatch(/^wss?:\/\/[^/]+\/codex\/api\/v4\/ws$/);
  });

  test("at the server root", async () => {
    globalThis.CODEX = { APP_PATH: "/" };
    const { APP_BASE, V4_BASE } = await import("@/api/v4/base");
    const { WS_URL_V4 } = await import("@/api/v4/notify");

    expect(APP_BASE).toBe("/");
    expect(V4_BASE).toBe("/api/v4/");
    expect(WS_URL_V4).toMatch(/^wss?:\/\/[^/]+\/api\/v4\/ws$/);
  });

  test("falls back to root when CODEX is absent", async () => {
    globalThis.CODEX = undefined;
    const { V4_BASE } = await import("@/api/v4/base");
    expect(V4_BASE).toBe("/api/v4/");
  });
});
