/*
 * The metadata store's tag editor name suggestions.
 *
 * The server returns at most a capped page of names containing the query,
 * plus whether that page is every match. A complete page for a shorter
 * prefix of the query already holds every answer, so it is reused instead
 * of asking again; an incomplete one only stands in while the query's own
 * request lands. The cache lives as long as the editor.
 */
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock(import("@/api/v4/admin"), async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, getTagNames: vi.fn() };
});

import * as API from "@/api/v4/admin";
import { useMetadataStore } from "@/stores/metadata";

const respond = (names, isComplete = true) =>
  API.getTagNames.mockResolvedValueOnce({
    data: { names, complete: isComplete },
  });

describe("metadata store tag name suggestions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("nothing is cached before a field asks", () => {
    const store = useMetadataStore();
    expect(store.tagNameChoices("publisher", {}, "")).toStrictEqual([]);
    expect(API.getTagNames).not.toHaveBeenCalled();
  });

  test("an exact hit is served from the cache", async () => {
    const store = useMetadataStore();
    respond(["DX Comics", "Marlow"]);
    await store.loadTagNames({ field: "publisher", q: "" });
    await store.loadTagNames({ field: "publisher", q: "" });

    expect(API.getTagNames).toHaveBeenCalledTimes(1);
    expect(API.getTagNames).toHaveBeenCalledWith(
      "publisher",
      { q: "" },
      { signal: expect.any(AbortSignal) },
    );
    expect(store.tagNameChoices("publisher", {}, "")).toStrictEqual([
      "DX Comics",
      "Marlow",
    ]);
    expect(store.tagNamesLoading.publisher).toBe(false);
  });

  test("a complete shorter prefix skips the request", async () => {
    const store = useMetadataStore();
    respond(["Burrowgirl", "Burrowman"]);
    await store.loadTagNames({ field: "characters", q: "Bur" });
    // Different case and a trailing space normalize onto the same prefix.
    await store.loadTagNames({ field: "characters", q: "burr " });

    expect(API.getTagNames).toHaveBeenCalledTimes(1);
    // Vuetify narrows the reused page itself.
    expect(store.tagNameChoices("characters", {}, "burr")).toStrictEqual([
      "Burrowgirl",
      "Burrowman",
    ]);
  });

  test("an incomplete prefix fetches and stands in meanwhile", async () => {
    const store = useMetadataStore();
    respond(["Alfred", "Burrowman"], false);
    await store.loadTagNames({ field: "characters", q: "" });

    const response = Promise.withResolvers();
    API.getTagNames.mockReturnValueOnce(response.promise);
    const loading = store.loadTagNames({ field: "characters", q: "Rowan" });

    expect(store.tagNamesLoading.characters).toBe(true);
    expect(store.tagNameChoices("characters", {}, "Rowan")).toStrictEqual([
      "Alfred",
      "Burrowman",
    ]);
    response.resolve({ data: { names: ["Rowan"], complete: true } });
    await loading;

    expect(API.getTagNames).toHaveBeenLastCalledWith(
      "characters",
      { q: "Rowan" },
      { signal: expect.any(AbortSignal) },
    );
    expect(store.tagNameChoices("characters", {}, "Rowan")).toStrictEqual([
      "Rowan",
    ]);
    expect(store.tagNamesLoading.characters).toBe(false);
  });

  test("scopes are cached apart and blank scope entries are dropped", async () => {
    const store = useMetadataStore();
    respond(["Verdigris"]);
    await store.loadTagNames({
      field: "imprint",
      scope: { publisher: "DX Comics" },
    });
    respond(["Max", "Verdigris"]);
    await store.loadTagNames({ field: "imprint", scope: { publisher: "" } });

    expect(API.getTagNames).toHaveBeenNthCalledWith(
      1,
      "imprint",
      { publisher: "DX Comics", q: "" },
      { signal: expect.any(AbortSignal) },
    );
    expect(API.getTagNames).toHaveBeenNthCalledWith(
      2,
      "imprint",
      { q: "" },
      { signal: expect.any(AbortSignal) },
    );
    expect(
      store.tagNameChoices("imprint", { publisher: "DX Comics" }, ""),
    ).toStrictEqual(["Verdigris"]);
    expect(store.tagNameChoices("imprint", {}, "")).toStrictEqual([
      "Max",
      "Verdigris",
    ]);
  });

  test("an aborted request is swallowed", async () => {
    const store = useMetadataStore();
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    API.getTagNames.mockRejectedValueOnce(
      new DOMException("aborted", "AbortError"),
    );
    await store.loadTagNames({ field: "genres", q: "" });

    expect(consoleError).not.toHaveBeenCalled();
    expect(store.tagNameChoices("genres", {}, "")).toStrictEqual([]);
    consoleError.mockRestore();
  });

  test("any other error is logged and leaves the field loadable", async () => {
    const store = useMetadataStore();
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    API.getTagNames.mockRejectedValueOnce(new Error("boom"));
    await store.loadTagNames({ field: "genres", q: "" });

    expect(consoleError).toHaveBeenCalledTimes(1);
    expect(store.tagNamesLoading.genres).toBe(false);
    consoleError.mockRestore();
  });

  test("a newer query aborts the stale one", async () => {
    const store = useMetadataStore();
    let staleSignal;
    API.getTagNames.mockImplementationOnce((_field, _params, { signal }) => {
      staleSignal = signal;
      return new Promise(() => {});
    });
    store.loadTagNames({ field: "teams", q: "a" });
    respond(["Avengards"]);
    await store.loadTagNames({ field: "teams", q: "av" });

    expect(staleSignal.aborted).toBe(true);
    expect(store.tagNameChoices("teams", {}, "av")).toStrictEqual([
      "Avengards",
    ]);
    expect(store.tagNamesLoading.teams).toBe(false);
  });

  test("clearMetadata clears the cache", async () => {
    const store = useMetadataStore();
    respond(["Horror"]);
    await store.loadTagNames({ field: "genres", q: "" });
    store.clearMetadata();

    expect(store.tagNames).toStrictEqual({});
    expect(store.tagNamesLoading).toStrictEqual({});
    expect(store.tagNameChoices("genres", {}, "")).toStrictEqual([]);
  });
});
